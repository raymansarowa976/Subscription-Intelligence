from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY

from .forms import ManualSubscriptionForm
from .models import (
    EmailConnection,
    EmailScanPreference,
    EmailScanRun,
    EmailSubscriptionLead,
    Subscription,
    SubscriptionCandidate,
    TransactionEvidence,
    TransactionImportRun,
)
from .services import (
    IngestionValidationError,
    InboxScanError,
    build_dashboard_context,
    calculate_next_renewal,
    classify_inbox_lead,
    infer_subscription_category,
    ingest_transactions,
    is_reviewable_inbox_lead,
    parse_request_json,
    record_failed_import_run,
    reviewable_inbox_confidence_threshold,
    scan_email_inbox_for_subscriptions,
)


def _parse_iso_date(value):
    if not value:
        return None
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _require_verified_session(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("accounts:verify_token")
    return None


def _is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


def _scan_status_label(scan):
    return dict(EmailScanRun.STATUS_CHOICES).get(scan.status, str(scan.status).replace("_", " ").title())


def _apply_candidate_filters(candidates, request):
    query = request.GET.get("q", "").strip()
    source = request.GET.get("source", "").strip()
    confidence = request.GET.get("confidence", "").strip()
    status = request.GET.get("status", "").strip()
    cadence = request.GET.get("cadence", "").strip()
    sort = request.GET.get("sort", "").strip()

    if query:
        candidates = candidates.filter(
            Q(merchant_name__icontains=query)
            | Q(normalized_vendor__icontains=query)
            | Q(source_email_lead__subject__icontains=query)
            | Q(source_email_lead__merchant_name__icontains=query)
        )
    if source:
        candidates = candidates.filter(source_type=source)
    if status:
        candidates = candidates.filter(status=status)
    if cadence:
        candidates = candidates.filter(cadence=cadence)
    if confidence == "high":
        candidates = candidates.filter(confidence_score__gte=80)
    elif confidence == "medium":
        candidates = candidates.filter(confidence_score__gte=50, confidence_score__lt=80)
    elif confidence == "low":
        candidates = candidates.filter(confidence_score__lt=50)

    ordering = {
        "confidence": "-confidence_score",
        "renewal_date": "likely_renewal_date",
        "amount": "-amount",
        "newest": "-created_at",
        "merchant": "merchant_name",
    }.get(sort, "-created_at")
    return candidates.order_by(ordering, "-id")


def _candidate_review_context(request, review_notice="", form_errors=None):
    user = request.user
    context = build_dashboard_context(user)
    candidates = SubscriptionCandidate.objects.filter(
        user=user,
        status=SubscriptionCandidate.STATUS_PENDING,
    ).filter(
        Q(source_type=SubscriptionCandidate.SOURCE_TRANSACTIONS)
        | Q(confidence_score__gte=reviewable_inbox_confidence_threshold())
    ).select_related("source_email_lead")
    context["candidates"] = _apply_candidate_filters(candidates, request)
    context["filtered_query_active"] = any(
        request.GET.get(key) for key in ["q", "source", "confidence", "status", "cadence", "sort"]
    )
    context["filtered_view"] = request.GET.get("view") == "filtered"
    filtered_leads = []
    for lead in EmailSubscriptionLead.objects.filter(user=user, status=EmailSubscriptionLead.STATUS_PENDING):
        classification, reason = classify_inbox_lead(lead)
        lead.classification = lead.classification or classification
        lead.classification_reason = lead.classification_reason or reason
        if not is_reviewable_inbox_lead(lead):
            filtered_leads.append(lead)
    context["filtered_inbox_leads"] = filtered_leads
    recent_scans = list(EmailScanRun.objects.filter(user=user).order_by("-created_at", "-id")[:6])
    for scan in recent_scans:
        scan.status_label = _scan_status_label(scan)
        scan.duration_seconds = max(0, int((scan.completed_at - scan.created_at).total_seconds()))
        scan.parser_candidate_count = SubscriptionCandidate.objects.filter(
            user=user,
            source_email_lead__scan_run=scan,
        ).count()
    context["recent_email_scans"] = recent_scans
    context["source_type_choices"] = SubscriptionCandidate.SOURCE_CHOICES
    context["candidate_status_choices"] = SubscriptionCandidate.STATUS_CHOICES
    context["cadence_choices"] = SubscriptionCandidate.CADENCE_CHOICES
    context["review_form_errors"] = form_errors or []
    context["review_notice"] = review_notice
    return context


def _candidate_review_partial(request, review_notice, form_errors=None):
    context = _candidate_review_context(request, review_notice, form_errors=form_errors)
    context["htmx_response"] = True
    return render(request, "subscriptions/_candidate_list.html", context)


def _inbox_scan_partial(request, scan_notice, scan_notice_level="success"):
    context = gmail_integrations_context(request.user)
    context["scan_notice"] = scan_notice
    context["scan_notice_level"] = scan_notice_level
    context["htmx_response"] = True
    return render(request, "subscriptions/_gmail_scan_panel.html", context)


def gmail_integrations_context(user):
    email_connections = EmailConnection.objects.filter(user=user)
    active_email_connection = email_connections.filter(status=EmailConnection.STATUS_ACTIVE).first()
    latest_scan = None
    if active_email_connection is not None:
        latest_scan = (
            EmailScanRun.objects.filter(user=user, email_connection=active_email_connection)
            .order_by("-created_at", "-id")
            .first()
        )
    scan_preferences, _ = EmailScanPreference.objects.get_or_create(user=user)
    return {
        "email_connections": email_connections,
        "active_email_connection": active_email_connection,
        "latest_gmail_scan": latest_scan,
        "privacy_controls": {
            "scan_scope": scan_preferences.scan_scope,
            "retention_period_days": str(scan_preferences.retention_period_days),
            "automatic_scans": scan_preferences.automatic_scans,
            "scan_intervals": scan_preferences.scan_intervals,
            "email_selection_rules": scan_preferences.email_selection_rules,
        },
    }


def data_sources_context(user):
    context = build_dashboard_context(user)
    recent_scans = list(EmailScanRun.objects.filter(user=user).order_by("-created_at", "-id")[:10])
    for scan in recent_scans:
        scan.status_label = _scan_status_label(scan)
        scan.duration_seconds = max(0, int((scan.completed_at - scan.created_at).total_seconds()))
        scan.parser_candidate_count = SubscriptionCandidate.objects.filter(
            user=user,
            source_email_lead__scan_run=scan,
        ).count()
        errors = scan.error_details.get("errors", []) if isinstance(scan.error_details, dict) else []
        scan.error_summary = ", ".join(str(error) for error in errors)
    context["recent_email_scans"] = recent_scans
    context["latest_sync"] = TransactionImportRun.objects.filter(user=user).first()
    context["email_connections"] = EmailConnection.objects.filter(user=user)
    return context


@login_required
def dashboard_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(request, "subscriptions/dashboard.html", build_dashboard_context(request.user))


@login_required
def gmail_integrations_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(request, "subscriptions/gmail_integrations.html", gmail_integrations_context(request.user))


@login_required
def analytics_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(request, "subscriptions/analytics.html", build_dashboard_context(request.user))


@login_required
def data_sources_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(request, "subscriptions/data_sources.html", data_sources_context(request.user))


def _filtered_subscriptions(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    subscriptions = Subscription.objects.filter(user=request.user)
    if query:
        subscriptions = subscriptions.filter(
            Q(merchant_name__icontains=query) | Q(normalized_vendor__icontains=query)
        )
    if category:
        subscriptions = subscriptions.filter(category=category)

    rows = list(subscriptions.order_by("merchant_name", "id"))
    for subscription in rows:
        subscription.dashboard_category = subscription.category or infer_subscription_category(
            subscription.merchant_name
        )
        subscription.dashboard_category_label = dict(Subscription.CATEGORY_CHOICES).get(
            subscription.dashboard_category,
            subscription.dashboard_category.title(),
        )
        subscription.dashboard_status_label = dict(Subscription.STATUS_CHOICES).get(
            subscription.status,
            subscription.status.title(),
        )
    return rows


@login_required
def subscription_results_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return render(
        request,
        "subscriptions/_subscription_results.html",
        {
            "subscriptions": _filtered_subscriptions(request),
        },
    )


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
        active_connection = EmailConnection.objects.filter(
            user=request.user,
            status=EmailConnection.STATUS_ACTIVE,
        ).first()
        if active_connection is not None:
            email_connection_id = str(active_connection.id)
        else:
            messages.info(request, "Connect Gmail to unlock inbox scanning.")
            return redirect("gmail_integrations")
    try:
        if email_connection_id:
            result = scan_email_inbox_for_subscriptions(request.user, email_connection_id=int(email_connection_id))
        else:
            result = scan_email_inbox_for_subscriptions(request.user)
    except InboxScanError as exc:
        if _is_htmx_request(request):
            return _inbox_scan_partial(request, str(exc), "error")
        messages.error(request, str(exc))
    else:
        if isinstance(result, dict) and result.get("status") == "failed":
            if _is_htmx_request(request):
                return _inbox_scan_partial(request, result.get("error", "Inbox scan failed."), "error")
            messages.error(request, result.get("error", "Inbox scan failed."))
            return redirect("gmail_integrations")
        success_message = (
            f"Inbox scan complete. Checked {result['scanned_message_count']} messages and found "
            f"{result['matched_message_count']} likely subscription emails."
        )
        if _is_htmx_request(request):
            return _inbox_scan_partial(request, success_message)
        messages.success(
            request,
            success_message,
        )
    return redirect("gmail_integrations")


def candidate_list_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    context = _candidate_review_context(request)
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

    now = timezone.now()
    dismissed_count = EmailSubscriptionLead.objects.filter(
        user=request.user,
        id__in=lead_ids,
        status=EmailSubscriptionLead.STATUS_PENDING,
    ).update(
        status=EmailSubscriptionLead.STATUS_DISMISSED,
        last_action="bulk_dismiss",
        last_action_at=now,
    )

    if _is_htmx_request(request):
        return _candidate_review_partial(request, f"{dismissed_count} inbox match dismissed")

    messages.info(request, f"{dismissed_count} {notice.lower()}.")
    return redirect("transactions:candidates")


def _candidate_edit_payload(request, candidate):
    if not any(key in request.POST for key in ["merchant_name", "amount", "cadence", "category", "next_renewal"]):
        return {}, []
    errors = []
    merchant_name = request.POST.get("merchant_name", "").strip()
    if not merchant_name:
        errors.append("Enter a merchant name")
    try:
        amount = Decimal(request.POST.get("amount", ""))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        amount = None
        errors.append("Enter a valid amount")
    currency = request.POST.get("currency", candidate.currency).strip().upper() or "USD"
    cadence = request.POST.get("cadence", "")
    if cadence not in dict(SubscriptionCandidate.CADENCE_CHOICES):
        errors.append("Choose a valid cadence")
    category = request.POST.get("category", infer_subscription_category(merchant_name or candidate.merchant_name))
    if category not in dict(Subscription.CATEGORY_CHOICES):
        errors.append("Choose a valid category")
    next_renewal = _parse_iso_date(request.POST.get("next_renewal", ""))
    if request.POST.get("next_renewal") and next_renewal is None:
        errors.append("Enter a valid renewal date")
    return {
        "merchant_name": merchant_name,
        "normalized_vendor": merchant_name.strip().lower(),
        "amount": amount,
        "currency": currency,
        "cadence": cadence,
        "category": category,
        "next_renewal": next_renewal,
    }, errors


@require_POST
def confirm_candidate_view(request, candidate_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    candidate = get_object_or_404(
        SubscriptionCandidate,
        pk=candidate_id,
        user=request.user,
    )
    if candidate.status == SubscriptionCandidate.STATUS_CONFIRMED:
        if _is_htmx_request(request):
            return _candidate_review_partial(request, "Subscription already saved")
        messages.info(request, "Subscription already saved")
        return redirect("dashboard")
    payload, form_errors = _candidate_edit_payload(request, candidate)
    if form_errors:
        if _is_htmx_request(request):
            return _candidate_review_partial(request, "", form_errors=form_errors)
        for error in form_errors:
            messages.error(request, error)
        return redirect("transactions:candidates")
    latest_transaction = (
        TransactionEvidence.objects.filter(
            user=request.user,
            provider_transaction_id__in=candidate.source_transaction_ids,
        )
        .order_by("-posted_at", "-id")
        .first()
    )
    merchant_name = payload.get("merchant_name", candidate.merchant_name)
    amount = payload.get("amount", candidate.amount)
    cadence = payload.get("cadence", candidate.cadence)
    next_renewal = payload.get(
        "next_renewal",
        candidate.likely_renewal_date
        if candidate.likely_renewal_date
        else calculate_next_renewal(latest_transaction.posted_at, candidate.cadence)
        if latest_transaction
        else None,
    )
    Subscription.objects.get_or_create(
        user=request.user,
        merchant_name=merchant_name,
        defaults={
            "normalized_vendor": payload.get("normalized_vendor", candidate.normalized_vendor),
            "amount": amount,
            "currency": payload.get("currency", candidate.currency),
            "cadence": cadence,
            "category": payload.get("category", infer_subscription_category(merchant_name)),
            "next_renewal": next_renewal,
        },
    )
    candidate.status = SubscriptionCandidate.STATUS_CONFIRMED
    candidate.reviewed_at = timezone.now()
    candidate.save(update_fields=["status", "reviewed_at"])
    if candidate.source_email_lead_id:
        EmailSubscriptionLead.objects.filter(pk=candidate.source_email_lead_id, user=request.user).update(
            status=EmailSubscriptionLead.STATUS_CONFIRMED,
            last_action="confirm_candidate",
            last_action_at=timezone.now(),
        )
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
    )
    if candidate.status == SubscriptionCandidate.STATUS_REJECTED:
        if _is_htmx_request(request):
            return _candidate_review_partial(request, "Candidate already dismissed")
        messages.info(request, "Candidate already dismissed")
        return redirect("dashboard")
    candidate.status = SubscriptionCandidate.STATUS_REJECTED
    candidate.reviewed_at = timezone.now()
    candidate.save(update_fields=["status", "reviewed_at"])
    if candidate.source_email_lead_id:
        EmailSubscriptionLead.objects.filter(pk=candidate.source_email_lead_id, user=request.user).update(
            status=EmailSubscriptionLead.STATUS_DISMISSED,
            last_action="reject_candidate",
            last_action_at=timezone.now(),
        )
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Candidate dismissed")
    messages.info(request, "Candidate dismissed")
    return redirect("dashboard")


@require_POST
def dismiss_inbox_lead_view(request, lead_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    lead = get_object_or_404(EmailSubscriptionLead, pk=lead_id, user=request.user)
    lead.status = EmailSubscriptionLead.STATUS_DISMISSED
    lead.last_action = "dismiss"
    lead.last_action_at = timezone.now()
    lead.save(update_fields=["status", "last_action", "last_action_at"])
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Inbox match dismissed")
    return redirect("transactions:candidates")


@require_POST
def mark_inbox_lead_newsletter_view(request, lead_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    lead = get_object_or_404(EmailSubscriptionLead, pk=lead_id, user=request.user)
    lead.classification = EmailSubscriptionLead.CLASSIFICATION_NEWSLETTER
    lead.classification_reason = "Marked as newsletter by user."
    lead.status = EmailSubscriptionLead.STATUS_DISMISSED
    lead.last_action = "mark_newsletter"
    lead.last_action_at = timezone.now()
    lead.save(update_fields=["classification", "classification_reason", "status", "last_action", "last_action_at"])
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Inbox match marked as newsletter")
    return redirect("transactions:candidates")


@require_POST
def restore_inbox_lead_view(request, lead_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    lead = get_object_or_404(EmailSubscriptionLead, pk=lead_id, user=request.user)
    lead.status = EmailSubscriptionLead.STATUS_PENDING
    lead.last_action = "restore"
    lead.last_action_at = timezone.now()
    lead.save(update_fields=["status", "last_action", "last_action_at"])
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Inbox match restored")
    return redirect("transactions:candidates")


@require_POST
def bulk_update_inbox_leads_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    lead_ids = request.POST.getlist("lead_ids")
    action = request.POST.get("action", "dismiss")
    leads = EmailSubscriptionLead.objects.filter(user=request.user, id__in=lead_ids)
    updates = {"last_action": f"bulk_{action}", "last_action_at": timezone.now()}
    if action == "restore":
        updates["status"] = EmailSubscriptionLead.STATUS_PENDING
    else:
        updates["status"] = EmailSubscriptionLead.STATUS_DISMISSED
    if action == "newsletter":
        updates["classification"] = EmailSubscriptionLead.CLASSIFICATION_NEWSLETTER
        updates["classification_reason"] = "Marked as newsletter by user."
    leads.update(**updates)
    if _is_htmx_request(request):
        return _candidate_review_partial(request, "Selected inbox matches updated")
    return redirect("transactions:candidates")


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
