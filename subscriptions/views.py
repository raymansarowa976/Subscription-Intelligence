from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY

from .models import Subscription, SubscriptionCandidate
from .services import ingest_transactions, parse_request_json


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
    subscriptions = Subscription.objects.filter(user=request.user, status=Subscription.STATUS_ACTIVE)
    candidates = SubscriptionCandidate.objects.filter(
        user=request.user,
        status=SubscriptionCandidate.STATUS_PENDING,
    )
    return render(
        request,
        "subscriptions/dashboard.html",
        {"subscriptions": subscriptions, "candidate_count": candidates.count()},
    )


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
    Subscription.objects.create(
        user=request.user,
        merchant_name=candidate.merchant_name,
        normalized_vendor=candidate.normalized_vendor,
        amount=candidate.amount,
        currency=candidate.currency,
        cadence=candidate.cadence,
    )
    candidate.status = SubscriptionCandidate.STATUS_CONFIRMED
    candidate.save(update_fields=["status"])
    messages.success(request, "Subscription saved")
    return redirect("dashboard")
