import json
import hashlib
import imaplib
import re
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, parseaddr
from itertools import groupby

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import (
    EmailScanRun,
    EmailSubscriptionLead,
    Subscription,
    SubscriptionCandidate,
    TransactionEvidence,
    TransactionImportRun,
)
from .receipt_parser import clean_email_html


def _normalize_vendor(name):
    return " ".join(name.strip().lower().split())


SUBSCRIPTION_EMAIL_KEYWORDS = [
    "subscription",
    "membership",
    "renewal",
    "billing",
    "invoice",
    "receipt",
    "payment",
    "charged",
    "charge",
    "autopay",
    "monthly",
    "annual",
    "plan",
    "trial",
]

SUBSCRIPTION_VENDOR_HINTS = [
    "netflix",
    "spotify",
    "youtube",
    "hulu",
    "disney",
    "apple",
    "adobe",
    "figma",
    "slack",
    "notion",
    "dropbox",
    "openai",
    "microsoft",
    "google one",
    "xbox",
    "playstation",
    "amazon prime",
    "prime video",
    "canva",
    "zoom",
    "verizon",
    "xfinity",
]

REVIEWABLE_INBOX_CONFIDENCE_THRESHOLD = 50

NEWSLETTER_TERMS = [
    "newsletter",
    "digest",
    "roundup",
    "weekly update",
    "daily update",
    "community update",
    "marketing",
    "unsubscribe",
]

NEWSLETTER_SENDERS = [
    "quincy larson",
    "freecodecamp",
    "mermaid",
]


class IngestionValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("Invalid ingestion payload")


class InboxScanError(Exception):
    pass


def record_failed_import_run(user, payload, errors):
    provider = str(payload.get("provider", "")).strip() or "unknown"
    account_id = str(payload.get("account_id", "")).strip() or "unknown"
    transaction_count = len(payload.get("transactions", [])) if isinstance(payload.get("transactions"), list) else 0
    return TransactionImportRun.objects.create(
        user=user,
        provider=provider,
        account_id=account_id,
        status=TransactionImportRun.STATUS_FAILED,
        requested_transaction_count=transaction_count,
        invalid_transactions=transaction_count,
        error_details={"errors": errors},
    )


def _build_dedupe_key(user_id, provider, account_id, normalized_merchant_name, amount, currency, posted_at):
    raw_key = "|".join(
        [
            str(user_id),
            provider.strip().lower(),
            account_id.strip().lower(),
            normalized_merchant_name,
            f"{Decimal(str(amount)):.2f}",
            currency.strip().upper(),
            posted_at.isoformat(),
        ]
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _validate_ingestion_payload(payload):
    errors = []
    provider = str(payload.get("provider", "")).strip()
    account_id = str(payload.get("account_id", "")).strip()
    transactions = payload.get("transactions")

    if not provider:
        errors.append({"field": "provider", "message": "This field is required."})
    if not account_id:
        errors.append({"field": "account_id", "message": "This field is required."})
    if not isinstance(transactions, list) or not transactions:
        errors.append({"field": "transactions", "message": "Provide a non-empty list of transactions."})

    normalized_transactions = []
    seen_provider_ids = set()

    if isinstance(transactions, list):
        for index, tx in enumerate(transactions):
            if not isinstance(tx, dict):
                errors.append({"field": f"transactions[{index}]", "message": "Each transaction must be an object."})
                continue

            row_errors = []
            provider_transaction_id = str(tx.get("provider_transaction_id", "")).strip()
            merchant_name = str(tx.get("merchant_name", "")).strip()
            description = str(tx.get("description", "")).strip()
            currency = str(tx.get("currency", "USD")).strip().upper() or "USD"

            if not provider_transaction_id:
                row_errors.append("provider_transaction_id is required.")
            elif provider_transaction_id in seen_provider_ids:
                row_errors.append("provider_transaction_id must be unique within the payload.")
            else:
                seen_provider_ids.add(provider_transaction_id)

            if not merchant_name:
                row_errors.append("merchant_name is required.")

            try:
                amount = Decimal(str(tx.get("amount", "")))
            except Exception:
                row_errors.append("amount must be a valid decimal value.")
                amount = None

            try:
                posted_at = date.fromisoformat(str(tx.get("posted_at", "")).strip())
            except Exception:
                row_errors.append("posted_at must use YYYY-MM-DD format.")
                posted_at = None

            if row_errors:
                errors.append(
                    {
                        "field": f"transactions[{index}]",
                        "message": " ".join(row_errors),
                    }
                )
                continue

            normalized_merchant_name = _normalize_vendor(merchant_name)
            normalized_transactions.append(
                {
                    "provider_transaction_id": provider_transaction_id,
                    "merchant_name": merchant_name,
                    "normalized_merchant_name": normalized_merchant_name,
                    "description": description,
                    "amount": amount,
                    "currency": currency,
                    "posted_at": posted_at,
                    "raw_payload": tx,
                }
            )

    if errors:
        raise IngestionValidationError(errors)

    return {
        "provider": provider,
        "account_id": account_id,
        "transactions": normalized_transactions,
    }


def _decode_email_header(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _strip_html_tags(value):
    return re.sub(r"\s+", " ", clean_email_html(value)).strip()


def _extract_email_body(message):
    body_parts = []

    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_filename():
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")
            if part.get_content_type() == "text/plain":
                body_parts.append(decoded)
            elif part.get_content_type() == "text/html" and not body_parts:
                body_parts.append(_strip_html_tags(decoded))
    else:
        payload = message.get_payload(decode=True)
        if payload:
            charset = message.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except LookupError:
                decoded = payload.decode("utf-8", errors="replace")
            if message.get_content_type() == "text/html":
                decoded = _strip_html_tags(decoded)
            body_parts.append(decoded)

    body = "\n".join(part.strip() for part in body_parts if part and part.strip())
    return body[:4000]


def _score_subscription_email(subject, sender_email, body):
    normalized = " ".join([subject, sender_email, body]).lower()
    keyword_hits = sum(1 for keyword in SUBSCRIPTION_EMAIL_KEYWORDS if keyword in normalized)
    vendor_hits = sum(1 for vendor in SUBSCRIPTION_VENDOR_HINTS if vendor in normalized)
    score = min(100, keyword_hits * 12 + vendor_hits * 18)
    if _looks_like_newsletter(subject=subject, sender=sender_email, snippet=body):
        score = min(score, 35)
    return score


def _looks_like_newsletter(*, subject="", sender="", sender_name="", snippet="", cleaned_body=""):
    normalized = " ".join([subject, sender, sender_name, snippet, cleaned_body]).lower()
    if any(sender_hint in normalized for sender_hint in NEWSLETTER_SENDERS):
        return True
    if any(term in normalized for term in NEWSLETTER_TERMS):
        billing_terms = {"invoice", "receipt", "charged", "payment", "billing date", "renews", "renewal date"}
        return not any(term in normalized for term in billing_terms)
    return False


def is_reviewable_inbox_lead(lead):
    return (
        lead.confidence_score >= REVIEWABLE_INBOX_CONFIDENCE_THRESHOLD
        and not _looks_like_newsletter(
            subject=lead.subject,
            sender=lead.sender,
            sender_name=lead.sender_name,
            snippet=lead.snippet,
            cleaned_body=lead.cleaned_body,
        )
    )


def _extract_merchant_name(sender_name, sender_email, subject, body):
    sender_name = sender_name.strip()
    if sender_name and sender_name.lower() not in {"no-reply", "noreply", "support", "billing"}:
        cleaned_sender_name = re.sub(
            r"(?i)\b(billing|payments|support|notifications|receipts?|team)\b",
            " ",
            sender_name,
        )
        cleaned_sender_name = re.sub(r"\s+", " ", cleaned_sender_name).strip(" -")
        if cleaned_sender_name:
            return cleaned_sender_name[:255]
        return sender_name[:255]

    normalized = " ".join([subject, sender_email, body]).lower()
    for vendor in SUBSCRIPTION_VENDOR_HINTS:
        if vendor in normalized:
            return vendor.title()

    domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else sender_email.lower()
    root = domain.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return (root.title() or "Email subscription lead")[:255]


def _parse_email_received_at(message):
    raw_date = message.get("Date", "")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            if parsed is not None:
                if timezone.is_naive(parsed):
                    return timezone.make_aware(parsed, timezone.get_current_timezone())
                return parsed.astimezone(timezone.get_current_timezone())
        except Exception:
            pass
    return timezone.now()


def _message_identifier(message, fallback_id):
    message_id = _decode_email_header(message.get("Message-ID", "")).strip()
    return (message_id or fallback_id)[:255]


def record_failed_email_scan_run(user, mailbox, errors):
    return EmailScanRun.objects.create(
        user=user,
        provider="imap",
        mailbox=mailbox,
        status=EmailScanRun.STATUS_FAILED,
        error_details={"errors": errors},
    )


def scan_email_inbox_for_subscriptions(user):
    username = getattr(settings, "IMAP_USERNAME", "").strip()
    password = getattr(settings, "IMAP_PASSWORD", "").strip()
    host = getattr(settings, "IMAP_HOST", "imap.gmail.com").strip()
    port = getattr(settings, "IMAP_PORT", 993)
    mailbox = getattr(settings, "IMAP_MAILBOX", "INBOX").strip() or "INBOX"
    lookback_days = max(1, getattr(settings, "EMAIL_SCAN_LOOKBACK_DAYS", 180))
    max_messages = max(1, getattr(settings, "EMAIL_SCAN_MAX_MESSAGES", 200))

    if not username or not password:
        raise InboxScanError("Inbox credentials are not configured. Set IMAP_USERNAME and IMAP_PASSWORD first.")

    connection = None
    scan_run = EmailScanRun.objects.create(
        user=user,
        provider="imap",
        mailbox=mailbox,
        status=EmailScanRun.STATUS_SUCCEEDED,
    )

    scanned_count = 0
    matched_count = 0
    created_count = 0
    since_date = (timezone.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")

    try:
        connection = imaplib.IMAP4_SSL(host, port)
        connection.login(username, password)
        status, _ = connection.select(mailbox)
        if status != "OK":
            raise InboxScanError(f"Unable to open mailbox {mailbox}.")

        status, message_ids = connection.search(None, "SINCE", since_date)
        if status != "OK":
            raise InboxScanError("Unable to search inbox messages.")

        identifiers = message_ids[0].split()[-max_messages:]
        scanned_count = len(identifiers)

        for identifier in identifiers:
            fetch_status, payload = connection.fetch(identifier, "(BODY.PEEK[])")
            if fetch_status != "OK":
                continue

            raw_message = None
            for item in payload:
                if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], (bytes, bytearray)):
                    raw_message = bytes(item[1])
                    break
            if not raw_message:
                continue

            message = message_from_bytes(raw_message)
            subject = _decode_email_header(message.get("Subject", "")).strip()[:255]
            sender_name, sender_email = parseaddr(_decode_email_header(message.get("From", "")))
            body = _extract_email_body(message)
            confidence_score = _score_subscription_email(subject, sender_email, body)
            if confidence_score < 30:
                continue

            merchant_name = _extract_merchant_name(sender_name, sender_email, subject, body)
            snippet_source = body or subject or sender_email
            snippet = re.sub(r"\s+", " ", snippet_source).strip()[:500]
            message_id = _message_identifier(message, f"{mailbox}:{identifier.decode('utf-8', errors='ignore')}")
            received_at = _parse_email_received_at(message)

            lead, created = EmailSubscriptionLead.objects.update_or_create(
                user=user,
                message_id=message_id,
                defaults={
                    "scan_run": scan_run,
                    "sender": sender_email[:255],
                    "sender_name": sender_name[:255],
                    "subject": subject or "(No subject)",
                    "merchant_name": merchant_name,
                    "snippet": snippet,
                    "cleaned_body": body,
                    "received_at": received_at,
                    "confidence_score": confidence_score,
                    "raw_headers": {
                        "from": _decode_email_header(message.get("From", ""))[:255],
                        "to": _decode_email_header(message.get("To", ""))[:255],
                        "date": _decode_email_header(message.get("Date", ""))[:255],
                    },
                },
            )
            from .tasks import parse_receipt_lead_task

            parse_receipt_lead_task(lead.id)
            matched_count += 1
            if created:
                created_count += 1

        scan_run.scanned_message_count = scanned_count
        scan_run.matched_message_count = matched_count
        scan_run.completed_at = timezone.now()
        scan_run.save(update_fields=["scanned_message_count", "matched_message_count", "completed_at"])
        return {
            "scan_run_id": scan_run.id,
            "provider": "imap",
            "mailbox": mailbox,
            "scanned_message_count": scanned_count,
            "matched_message_count": matched_count,
            "new_lead_count": created_count,
        }
    except InboxScanError:
        scan_run.status = EmailScanRun.STATUS_FAILED
        scan_run.error_details = {"errors": ["Inbox scan failed."]}
        scan_run.completed_at = timezone.now()
        scan_run.save(update_fields=["status", "error_details", "completed_at"])
        raise
    except imaplib.IMAP4.error as exc:
        scan_run.status = EmailScanRun.STATUS_FAILED
        scan_run.error_details = {"errors": [str(exc)]}
        scan_run.completed_at = timezone.now()
        scan_run.save(update_fields=["status", "error_details", "completed_at"])
        raise InboxScanError("Inbox login failed. Check your IMAP credentials or app password.") from exc
    except Exception as exc:
        scan_run.status = EmailScanRun.STATUS_FAILED
        scan_run.error_details = {"errors": [str(exc)]}
        scan_run.completed_at = timezone.now()
        scan_run.save(update_fields=["status", "error_details", "completed_at"])
        raise InboxScanError("Inbox scan failed unexpectedly.") from exc
    finally:
        if connection is not None:
            try:
                connection.logout()
            except Exception:
                pass


def infer_subscription_category(vendor_name):
    normalized_vendor = _normalize_vendor(vendor_name)
    if any(keyword in normalized_vendor for keyword in ["spotify", "apple music", "tidal", "pandora"]):
        return Subscription.CATEGORY_MUSIC
    if any(keyword in normalized_vendor for keyword in ["netflix", "hulu", "disney", "max", "prime video", "youtube tv"]):
        return Subscription.CATEGORY_STREAMING
    if any(keyword in normalized_vendor for keyword in ["adobe", "notion", "slack", "figma", "openai", "dropbox", "microsoft"]):
        return Subscription.CATEGORY_SOFTWARE
    if any(keyword in normalized_vendor for keyword in ["verizon", "at&t", "tmobile", "comcast", "xfinity", "utility", "power", "water", "gas", "internet"]):
        return Subscription.CATEGORY_UTILITIES
    return Subscription.CATEGORY_OTHER


def _infer_cadence(dates):
    if len(dates) < 2:
        return None
    ordered = sorted(dates, reverse=True)
    delta_days = (ordered[0] - ordered[1]).days
    if 28 <= delta_days <= 35:
        return SubscriptionCandidate.CADENCE_MONTHLY
    if 360 <= delta_days <= 370:
        return SubscriptionCandidate.CADENCE_YEARLY
    return None


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def calculate_next_renewal(last_charge_date, cadence):
    if cadence == SubscriptionCandidate.CADENCE_YEARLY or cadence == "yearly":
        return date(
            last_charge_date.year + 1,
            last_charge_date.month,
            min(last_charge_date.day, monthrange(last_charge_date.year + 1, last_charge_date.month)[1]),
        )
    return _add_months(last_charge_date, 1)


def find_latest_transaction_for_subscription(subscription):
    return (
        TransactionEvidence.objects.filter(
            user=subscription.user,
            merchant_name__iexact=subscription.merchant_name,
            amount=subscription.amount,
            currency=subscription.currency,
        )
        .order_by("-posted_at", "-id")
        .first()
    )


def infer_subscription_next_renewal(subscription):
    if subscription.next_renewal:
        return subscription.next_renewal
    latest_transaction = find_latest_transaction_for_subscription(subscription)
    if latest_transaction is None:
        return None
    return calculate_next_renewal(latest_transaction.posted_at, subscription.cadence)


def monthly_amount_for_subscription(subscription):
    if subscription.cadence == SubscriptionCandidate.CADENCE_YEARLY or subscription.cadence == "yearly":
        return subscription.amount / Decimal("12")
    return subscription.amount


def annual_amount_for_subscription(subscription):
    if subscription.cadence == SubscriptionCandidate.CADENCE_YEARLY or subscription.cadence == "yearly":
        return subscription.amount
    return subscription.amount * Decimal("12")


def _subscription_sort_key(subscription):
    next_renewal = infer_subscription_next_renewal(subscription)
    return (
        0 if subscription.status == Subscription.STATUS_ACTIVE else 1,
        next_renewal or date.max,
        subscription.merchant_name.lower(),
        subscription.id,
    )


def build_dashboard_context(user):
    today = date.today()
    subscriptions = list(Subscription.objects.filter(user=user))
    candidates = list(
        SubscriptionCandidate.objects.filter(
            user=user,
            status=SubscriptionCandidate.STATUS_PENDING,
        ).order_by("-created_at")
    )
    latest_sync = TransactionImportRun.objects.filter(user=user).first()
    latest_email_scan = EmailScanRun.objects.filter(user=user).first()
    pending_inbox_leads = list(
        EmailSubscriptionLead.objects.filter(
            user=user,
            status=EmailSubscriptionLead.STATUS_PENDING,
        ).prefetch_related("subscription_candidates")
    )
    reviewable_inbox_leads = []
    suppressed_inbox_lead_count = 0
    for lead in pending_inbox_leads:
        if not is_reviewable_inbox_lead(lead):
            suppressed_inbox_lead_count += 1
            continue
        lead.review_candidate = next(
            (
                candidate
                for candidate in lead.subscription_candidates.all()
                if candidate.status == SubscriptionCandidate.STATUS_PENDING
            ),
            None,
        )
        reviewable_inbox_leads.append(lead)

    renewal_entries = []
    for subscription in subscriptions:
        next_renewal = infer_subscription_next_renewal(subscription)
        subscription.dashboard_category = subscription.category or infer_subscription_category(subscription.merchant_name)
        subscription.dashboard_category_label = dict(Subscription.CATEGORY_CHOICES).get(
            subscription.dashboard_category,
            subscription.dashboard_category.title(),
        )
        subscription.dashboard_next_renewal = next_renewal
        subscription.dashboard_status_label = dict(Subscription.STATUS_CHOICES).get(
            subscription.status,
            subscription.status.title(),
        )
        renewal_entries.append(
            {
                "subscription": subscription,
                "next_renewal": next_renewal,
                "monthly_amount": monthly_amount_for_subscription(subscription),
                "annual_amount": annual_amount_for_subscription(subscription),
            }
        )

    subscriptions.sort(key=_subscription_sort_key)
    active_entries = [
        entry for entry in renewal_entries if entry["subscription"].status == Subscription.STATUS_ACTIVE
    ]

    total_monthly_spend = sum((entry["monthly_amount"] for entry in active_entries), Decimal("0.00"))
    annual_run_rate = sum((entry["annual_amount"] for entry in active_entries), Decimal("0.00"))
    upcoming_entries = [
        entry
        for entry in active_entries
        if entry["next_renewal"] and today <= entry["next_renewal"] <= today + timedelta(days=7)
    ]
    upcoming_renewals_cost = sum((entry["subscription"].amount for entry in upcoming_entries), Decimal("0.00"))
    next_five_renewals = sorted(
        [entry for entry in active_entries if entry["next_renewal"]],
        key=lambda entry: entry["next_renewal"],
    )[:5]

    category_totals = defaultdict(lambda: Decimal("0.00"))
    for entry in active_entries:
        category = entry["subscription"].dashboard_category
        category_totals[category] += entry["monthly_amount"]

    category_labels = []
    category_values = []
    for category, amount in category_totals.items():
        category_labels.append(dict(Subscription.CATEGORY_CHOICES).get(category, category.title()))
        category_values.append(float(amount))

    trend_rows = (
        TransactionEvidence.objects.filter(user=user, posted_at__gte=_add_months(today.replace(day=1), -5))
        .annotate(month=TruncMonth("posted_at"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    trend_map = {
        row["month"].strftime("%b"): float(row["total"] or 0)
        for row in trend_rows
        if row["month"] is not None
    }
    trend_labels = []
    trend_values = []
    for month_offset in range(-5, 1):
        month_date = _add_months(today.replace(day=1), month_offset)
        label = month_date.strftime("%b")
        trend_labels.append(label)
        trend_values.append(trend_map.get(label, 0))

    savings_insights = []
    sortable_entries = sorted(
        active_entries,
        key=lambda entry: (
            entry["subscription"].dashboard_category,
            entry["subscription"].merchant_name.lower(),
        ),
    )
    for category, grouped_entries in groupby(
        sortable_entries,
        key=lambda entry: entry["subscription"].dashboard_category,
    ):
        grouped_entries = list(grouped_entries)
        if len(grouped_entries) < 2:
            continue
        if category not in {Subscription.CATEGORY_STREAMING, Subscription.CATEGORY_MUSIC, Subscription.CATEGORY_SOFTWARE}:
            continue
        category_label = dict(Subscription.CATEGORY_CHOICES).get(category, category.title())
        savings_insights.append(
            {
                "title": f"You have {len(grouped_entries)} {category_label.lower()} subscriptions",
                "detail": f"They add up to ${sum((entry['monthly_amount'] for entry in grouped_entries), Decimal('0.00')):.2f} per month. Consider whether any overlap can be removed.",
            }
        )

    display_name = user.first_name or user.username
    featured_subscription = subscriptions[0] if subscriptions else None
    inbox_lead_count = len(reviewable_inbox_leads)
    active_subscription_count = len(
        [subscription for subscription in subscriptions if subscription.status == Subscription.STATUS_ACTIVE]
    )
    inactive_subscription_count = len(
        [subscription for subscription in subscriptions if subscription.status != Subscription.STATUS_ACTIVE]
    )
    show_dashboard_zero_state = (
        active_subscription_count == 0
        and inactive_subscription_count == 0
        and len(candidates) == 0
        and inbox_lead_count == 0
    )

    return {
        "subscriptions": subscriptions,
        "active_subscription_count": active_subscription_count,
        "inactive_subscription_count": inactive_subscription_count,
        "featured_subscription": featured_subscription,
        "candidate_count": len(candidates),
        "recent_candidates": candidates[:3],
        "total_monthly_spend": total_monthly_spend,
        "upcoming_renewals_cost": upcoming_renewals_cost,
        "annual_run_rate": annual_run_rate,
        "upcoming_renewal_count": len(upcoming_entries),
        "next_five_renewals": next_five_renewals,
        "category_labels": category_labels,
        "category_values": category_values,
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "savings_insights": savings_insights[:2],
        "display_name": display_name,
        "latest_sync": latest_sync,
        "latest_email_scan": latest_email_scan,
        "inbox_leads": reviewable_inbox_leads[:5],
        "inbox_lead_count": inbox_lead_count,
        "suppressed_inbox_lead_count": suppressed_inbox_lead_count,
        "reviewable_inbox_confidence_threshold": REVIEWABLE_INBOX_CONFIDENCE_THRESHOLD,
        "show_dashboard_zero_state": show_dashboard_zero_state,
    }


@transaction.atomic
def ingest_transactions(user, payload):
    normalized_payload = _validate_ingestion_payload(payload)
    provider = normalized_payload["provider"]
    account_id = normalized_payload["account_id"]
    transactions = normalized_payload["transactions"]
    ingested = 0
    duplicates = 0
    invalid = 0

    import_run = TransactionImportRun.objects.create(
        user=user,
        provider=provider,
        account_id=account_id,
        status=TransactionImportRun.STATUS_SUCCEEDED,
        requested_transaction_count=len(transactions),
    )

    for tx in transactions:
        dedupe_key = _build_dedupe_key(
            user.id,
            provider,
            account_id,
            tx["normalized_merchant_name"],
            tx["amount"],
            tx["currency"],
            tx["posted_at"],
        )
        existing_duplicate = TransactionEvidence.objects.filter(
            user=user,
            provider=provider,
            account_id=account_id,
            dedupe_key=dedupe_key,
        ).exists()
        if existing_duplicate:
            duplicates += 1
            continue
        _, created = TransactionEvidence.objects.get_or_create(
            provider_transaction_id=tx["provider_transaction_id"],
            defaults={
                "user": user,
                "import_run": import_run,
                "provider": provider,
                "account_id": account_id,
                "merchant_name": tx["merchant_name"],
                "normalized_merchant_name": tx["normalized_merchant_name"],
                "description": tx.get("description", ""),
                "amount": tx["amount"],
                "currency": tx.get("currency", "USD"),
                "posted_at": tx["posted_at"],
                "raw_payload": tx["raw_payload"],
                "dedupe_key": dedupe_key,
            },
        )
        if created:
            ingested += 1
        else:
            duplicates += 1

    import_run.ingested_transactions = ingested
    import_run.duplicate_transactions = duplicates
    import_run.invalid_transactions = invalid
    import_run.completed_at = timezone.now()
    import_run.save(
        update_fields=[
            "ingested_transactions",
            "duplicate_transactions",
            "invalid_transactions",
            "completed_at",
        ]
    )

    rebuild_subscription_candidates(user)
    return {
        "status": "accepted",
        "provider": provider,
        "account_id": account_id,
        "import_run_id": import_run.id,
        "ingested_transactions": ingested,
        "duplicate_transactions": duplicates,
        "invalid_transactions": invalid,
    }


def rebuild_subscription_candidates(user):
    evidence = TransactionEvidence.objects.filter(user=user).order_by("-posted_at", "-id")
    groups = defaultdict(list)
    for tx in evidence:
        groups[(_normalize_vendor(tx.merchant_name), tx.amount, tx.currency)].append(tx)

    SubscriptionCandidate.objects.filter(
        user=user,
        status=SubscriptionCandidate.STATUS_PENDING,
    ).delete()

    for (normalized_vendor, amount, currency), txs in groups.items():
        cadence = _infer_cadence([tx.posted_at for tx in txs])
        if cadence is None:
            continue
        SubscriptionCandidate.objects.create(
            user=user,
            merchant_name=txs[0].merchant_name,
            normalized_vendor=normalized_vendor,
            amount=amount,
            currency=currency,
            cadence=cadence,
            source_transaction_ids=[tx.provider_transaction_id for tx in txs[:12]],
        )


def parse_request_json(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise IngestionValidationError(
            [{"field": "body", "message": f"Invalid JSON payload: {exc.msg}."}]
        ) from exc
    if not isinstance(payload, dict):
        raise IngestionValidationError(
            [{"field": "body", "message": "The request body must be a JSON object."}]
        )
    return payload
