from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY

from .forms import ManualSubscriptionForm
from .models import EmailSubscriptionLead, Subscription, SubscriptionCandidate, TransactionEvidence
from .services import (
    IngestionValidationError,
    InboxScanError,
    build_dashboard_context,
    calculate_next_renewal,
    infer_subscription_category,
    ingest_transactions,
    is_reviewable_inbox_lead,
    parse_request_json,
    record_failed_import_run,
)
from .tasks import scan_email_inbox_task


def _require_verified_session(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("accounts:verify_token")
    return None


def _is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


def _candidate_review_context(user, review_notice=""):
    context = build_dashboard_context(user)
    context["candidates"] = SubscriptionCandidate.objects.filter(
        user=user,
        status=SubscriptionCandidate.STATUS_PENDING,
    )
    context["review_notice"] = review_notice
    return context


def _candidate_review_partial(request, review_notice):
    context = _candidate_review_context(request.user, review_notice)
    context["htmx_response"] = True
    return render(request, "subscriptions/_candidate_list.html", context)


def _inbox_scan_partial(request, scan_notice, scan_notice_level="success"):
    context = build_dashboard_context(request.user)
    context["scan_notice"] = scan_notice
    context["scan_notice_level"] = scan_notice_level
    context["htmx_response"] = True
    return render(request, "subscriptions/_inbox_scan_panel.html", context)


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
    try:
        payload = parse_request_json(request)
        response_payload = ingest_transactions(request.user, payload)
    except IngestionValidationError as exc:
        request_payload = payload if "payload" in locals() else {}
        import_run = record_failed_import_run(request.user, request_payload, exc.errors)
        return JsonResponse(
            {
                "status": "rejected",
                "import_run_id": import_run.id,
                "errors": exc.errors,
            },
            status=400,
        )
    return JsonResponse(response_payload, status=202)


@require_POST
def scan_inbox_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    email_connection_id = request.POST.get("email_connection_id") or None
    if email_connection_id is None:
        from .models import EmailConnection

        active_connection = EmailConnection.objects.filter(
            user=request.user,
            status=EmailConnection.STATUS_ACTIVE,
        ).first()
        if active_connection is not None:
            email_connection_id = str(active_connection.id)
    try:
        if email_connection_id:
            result = scan_email_inbox_task(request.user.id, int(email_connection_id))
        else:
            result = scan_email_inbox_task(request.user.id)
        if getattr(settings, "HUEY", {}).get("immediate") and hasattr(result, "get"):
            result = result.get(blocking=True)
    except InboxScanError as exc:
        if _is_htmx_request(request):
            return _inbox_scan_partial(request, str(exc), "error")
        messages.error(request, str(exc))
    else:
        if isinstance(result, dict) and result.get("status") == "failed":
            if _is_htmx_request(request):
                return _inbox_scan_partial(request, result.get("error", "Inbox scan failed."), "error")
            messages.error(request, result.get("error", "Inbox scan failed."))
            return redirect("transactions:candidates")
        if isinstance(result, dict):
            success_message = (
                f"Inbox scan complete. Checked {result['scanned_message_count']} messages and found "
                f"{result['matched_message_count']} likely subscription emails."
            )
        else:
            success_message = "Inbox scan queued. Refresh this page in a moment to review new matches."
        if _is_htmx_request(request):
            return _inbox_scan_partial(request, success_message)
        messages.success(
            request,
            success_message,
        )
    return redirect("transactions:candidates")


def candidate_list_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    context = _candidate_review_context(request.user)
    return render(request, "subscriptions/candidates.html", context)


@require_POST
def bulk_dismiss_inbox_leads_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    action = request.POST.get("action", "noise")
    pending_leads = list(
        EmailSubscriptionLead.objects.filter(
            user=request.user,
            status=EmailSubscriptionLead.STATUS_PENDING,
        )
    )
    if action == "all":
        lead_ids = [lead.id for lead in pending_leads]
        notice = "Inbox matches dismissed"
    else:
        lead_ids = [lead.id for lead in pending_leads if not is_reviewable_inbox_lead(lead)]
        notice = "Low-confidence and newsletter matches dismissed"

    dismissed_count = EmailSubscriptionLead.objects.filter(
        user=request.user,
        id__in=lead_ids,
        status=EmailSubscriptionLead.STATUS_PENDING,
    ).update(status=EmailSubscriptionLead.STATUS_DISMISSED)

    if _is_htmx_request(request):
        context = _candidate_review_context(request.user, f"{dismissed_count} inbox match dismissed")
        return render(request, "subscriptions/_candidate_list.html", context)

    messages.info(request, f"{dismissed_count} {notice.lower()}.")
    return redirect("transactions:candidates")


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
            candidate.likely_renewal_date
            if candidate.likely_renewal_date
            else
            calculate_next_renewal(latest_transaction.posted_at, candidate.cadence)
            if latest_transaction
            else None
        ),
    )
    candidate.status = SubscriptionCandidate.STATUS_CONFIRMED
    candidate.save(update_fields=["status"])
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Subscription saved")
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
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Candidate dismissed")
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
