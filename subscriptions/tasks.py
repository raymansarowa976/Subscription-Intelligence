from datetime import date, timedelta

from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailSubscriptionLead, Subscription, SubscriptionCandidate
from .receipt_parser import parse_receipt_text
from .services import InboxScanError, _normalize_vendor, scan_email_inbox_for_subscriptions


MIN_REVIEW_CANDIDATE_CONFIDENCE = 45
RENEWAL_ALERT_LOOKAHEAD_DAYS = 2


@db_task()
def scan_email_inbox_task(user_id):
    user = get_user_model().objects.get(pk=user_id)
    try:
        return scan_email_inbox_for_subscriptions(user)
    except InboxScanError as exc:
        return {"status": "failed", "error": str(exc)}


@db_task()
def parse_receipt_lead_task(email_lead_id):
    lead = EmailSubscriptionLead.objects.select_related("user").filter(pk=email_lead_id).first()
    if lead is None:
        return {"status": "missing_lead", "email_lead_id": email_lead_id}

    extraction = parse_receipt_text(
        lead.cleaned_body or lead.snippet,
        subject=lead.subject,
        sender_name=lead.sender_name,
        sender_email=lead.sender,
        received_at=lead.received_at,
    )

    if not extraction.has_required_candidate_fields or extraction.confidence_score < MIN_REVIEW_CANDIDATE_CONFIDENCE:
        return {
            "status": "review_only_no_candidate",
            "email_lead_id": lead.id,
            "confidence_score": extraction.confidence_score,
            "parser_version": extraction.parser_version,
            "raw_entity_metadata": extraction.raw_entity_metadata,
        }

    candidate, created = SubscriptionCandidate.objects.update_or_create(
        user=lead.user,
        source_email_lead=lead,
        defaults={
            "source_type": SubscriptionCandidate.SOURCE_EMAIL_RECEIPT,
            "merchant_name": extraction.merchant_name,
            "normalized_vendor": _normalize_vendor(extraction.merchant_name),
            "amount": extraction.amount,
            "currency": extraction.currency,
            "cadence": extraction.cadence,
            "status": SubscriptionCandidate.STATUS_PENDING,
            "source_transaction_ids": [],
            "billing_date": extraction.billing_date,
            "likely_renewal_date": extraction.likely_renewal_date,
            "confidence_score": extraction.confidence_score,
            "parser_version": extraction.parser_version,
            "raw_entity_metadata": extraction.raw_entity_metadata,
        },
    )
    return {
        "status": "created" if created else "updated",
        "candidate_id": candidate.id,
        "email_lead_id": lead.id,
        "confidence_score": extraction.confidence_score,
        "parser_version": extraction.parser_version,
    }


def subscriptions_renewing_in_48_hours(reference_date=None):
    target_date = (reference_date or timezone.localdate()) + timedelta(days=RENEWAL_ALERT_LOOKAHEAD_DAYS)
    return Subscription.objects.select_related("user").filter(
        status=Subscription.STATUS_ACTIVE,
        next_renewal=target_date,
        user__email__gt="",
    )


def send_renewal_alerts(reference_date=None):
    sent_count = 0
    alerted_subscription_ids = []

    for subscription in subscriptions_renewing_in_48_hours(reference_date):
        try:
            renewal_date = subscription.next_renewal.strftime("%B %-d, %Y")
        except ValueError:
            renewal_date = subscription.next_renewal.strftime("%B %#d, %Y")
        amount = f"${subscription.amount:.2f}"
        send_mail(
            subject=f"{subscription.merchant_name} renews in 48 hours",
            message=(
                f"{subscription.merchant_name} is scheduled to renew on {renewal_date}.\n\n"
                f"Amount: {amount} {subscription.currency}\n"
                f"Renewal date: {renewal_date}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscription.user.email],
            fail_silently=False,
        )
        sent_count += 1
        alerted_subscription_ids.append(subscription.id)

    return {
        "status": "completed",
        "target_date": (
            (reference_date or timezone.localdate()) + timedelta(days=RENEWAL_ALERT_LOOKAHEAD_DAYS)
        ).isoformat(),
        "sent_count": sent_count,
        "subscription_ids": alerted_subscription_ids,
    }


@db_task()
def send_renewal_alerts_task(reference_date_iso=None):
    reference_date = date.fromisoformat(reference_date_iso) if reference_date_iso else None
    return send_renewal_alerts(reference_date)


@db_periodic_task(crontab(minute="0", hour="9"))
def send_daily_renewal_alerts_task():
    return send_renewal_alerts()
