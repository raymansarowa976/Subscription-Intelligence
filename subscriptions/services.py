import json
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby

from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import TruncMonth

from .models import Subscription, SubscriptionCandidate, TransactionEvidence


def _normalize_vendor(name):
    return " ".join(name.strip().lower().split())


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
    latest_sync = (
        TransactionEvidence.objects.filter(user=user).order_by("-created_at").values_list("created_at", flat=True).first()
    )

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
    return {
        "subscriptions": subscriptions,
        "active_subscription_count": len(
            [subscription for subscription in subscriptions if subscription.status == Subscription.STATUS_ACTIVE]
        ),
        "inactive_subscription_count": len(
            [subscription for subscription in subscriptions if subscription.status != Subscription.STATUS_ACTIVE]
        ),
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
    }


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
