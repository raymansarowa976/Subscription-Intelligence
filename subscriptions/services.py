import json
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import SubscriptionCandidate, TransactionEvidence


def _normalize_vendor(name):
    return " ".join(name.strip().lower().split())


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


@transaction.atomic
def ingest_transactions(user, payload):
    provider = payload["provider"]
    account_id = payload["account_id"]
    ingested = 0
    duplicates = 0

    for tx in payload.get("transactions", []):
        _, created = TransactionEvidence.objects.get_or_create(
            provider_transaction_id=tx["provider_transaction_id"],
            defaults={
                "user": user,
                "provider": provider,
                "account_id": account_id,
                "merchant_name": tx["merchant_name"],
                "description": tx.get("description", ""),
                "amount": Decimal(str(tx["amount"])),
                "currency": tx.get("currency", "USD"),
                "posted_at": date.fromisoformat(tx["posted_at"]),
            },
        )
        if created:
            ingested += 1
        else:
            duplicates += 1

    rebuild_subscription_candidates(user)
    return {"status": "accepted", "provider": provider, "ingested_transactions": ingested, "duplicate_transactions": duplicates}


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
    return json.loads(request.body.decode("utf-8"))
