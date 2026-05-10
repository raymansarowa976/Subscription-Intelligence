from huey.contrib.djhuey import db_task

from .models import EmailSubscriptionLead, SubscriptionCandidate
from .receipt_parser import parse_receipt_text
from .services import _normalize_vendor


MIN_REVIEW_CANDIDATE_CONFIDENCE = 45


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
