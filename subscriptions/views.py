from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY

from .forms import ManualSubscriptionForm
from .models import Subscription, SubscriptionCandidate, TransactionEvidence
from .services import (
    build_dashboard_context,
    calculate_next_renewal,
    infer_subscription_category,
    ingest_transactions,
    parse_request_json,
)


def _require_verified_session(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("accounts:verify_token")
    return None


@login_required
def dashboard_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(request, "subscriptions/dashboard.html", build_dashboard_context(request.user))


@require_POST
def ingest_transactions_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    payload = ingest_transactions(request.user, parse_request_json(request))
    return JsonResponse(payload, status=202)


def candidate_list_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    candidates = SubscriptionCandidate.objects.filter(
        user=request.user,
        status=SubscriptionCandidate.STATUS_PENDING,
    )
    return render(request, "subscriptions/candidates.html", {"candidates": candidates})


@require_POST
def confirm_candidate_view(request, candidate_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    candidate = get_object_or_404(
        SubscriptionCandidate,
        pk=candidate_id,
        user=request.user,
        status=SubscriptionCandidate.STATUS_PENDING,
    )
    latest_transaction = (
        TransactionEvidence.objects.filter(
            user=request.user,
            provider_transaction_id__in=candidate.source_transaction_ids,
        )
        .order_by("-posted_at", "-id")
        .first()
    )
    Subscription.objects.create(
        user=request.user,
        merchant_name=candidate.merchant_name,
        normalized_vendor=candidate.normalized_vendor,
        amount=candidate.amount,
        currency=candidate.currency,
        cadence=candidate.cadence,
        category=infer_subscription_category(candidate.merchant_name),
        next_renewal=(
            calculate_next_renewal(latest_transaction.posted_at, candidate.cadence)
            if latest_transaction
            else None
        ),
    )
    candidate.status = SubscriptionCandidate.STATUS_CONFIRMED
    candidate.save(update_fields=["status"])
    messages.success(request, "Subscription saved")
    return redirect("dashboard")


@require_POST
def reject_candidate_view(request, candidate_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    candidate = get_object_or_404(
        SubscriptionCandidate,
        pk=candidate_id,
        user=request.user,
        status=SubscriptionCandidate.STATUS_PENDING,
    )
    candidate.status = SubscriptionCandidate.STATUS_REJECTED
    candidate.save(update_fields=["status"])
    messages.info(request, "Candidate dismissed")
    return redirect("dashboard")


def add_subscription_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    form = ManualSubscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        subscription = form.save(commit=False)
        subscription.user = request.user
        subscription.normalized_vendor = subscription.merchant_name.strip().lower()
        subscription.status = Subscription.STATUS_ACTIVE
        subscription.save()
        messages.success(request, "Subscription added")
        return redirect("dashboard")
    return render(request, "subscriptions/add_subscription.html", {"form": form})
