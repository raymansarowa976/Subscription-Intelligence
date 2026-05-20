from django.contrib import messages
import json
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sessions.models import Session
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.http import require_POST

from subscriptions.models import (
    EmailConnection,
    EmailScanRun,
    EmailScanPreference,
    EmailSubscriptionLead,
    Subscription,
    SubscriptionCandidate,
    TransactionEvidence,
    TransactionImportRun,
)
from subscriptions.tasks import scan_email_inbox_task

from .authentication_forms import SubscriptionAuthenticationForm
from .forms import (
    AccountRecoveryForm,
    LoginTokenVerificationForm,
    PasswordChangeForm,
    PasswordResetConfirmForm,
    ResendTokenForm,
    SignupForm,
    UsernameChangeRequestForm,
    UsernameChangeTokenForm,
)
from .rate_limiter import (
    RATE_LIMIT_MESSAGE,
    clear_attempts,
    get_client_ip,
    is_rate_limited,
    record_attempt,
)
from .token_service import clear_email_token, issue_email_token, verify_email_token


User = get_user_model()
logger = logging.getLogger(__name__)
LOGIN_TOKEN_VERIFIED_SESSION_KEY = "login_token_verified"
LEGACY_REACTIVATION_SESSION_KEY = "legacy_reactivation_user_id"
USERNAME_CHANGE_TOKEN_PURPOSE = "username-change"
PENDING_USERNAME_SESSION_KEY = "pending_username_change"
GMAIL_OAUTH_STATE_SESSION_KEY = "gmail_oauth_state"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
LOGIN_RATE_LIMIT = 5
RECOVERY_RATE_LIMIT = 5
TOKEN_VERIFY_RATE_LIMIT = 5
TOKEN_RESEND_RATE_LIMIT = 3
RATE_LIMIT_WINDOW_SECONDS = 900


@requires_csrf_token
def csrf_failure_view(request, reason=""):
    messages.error(request, "Your sign-in session expired. Please try again.")
    return render(request, "registration/login.html", {"form": SubscriptionAuthenticationForm(request)})


def _require_verified_session(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("accounts:verify_token")
    return None


def send_verification_token_email(user):
    token = issue_email_token(user.email)
    send_mail(
        "Your Subscription Intelligence login token",
        (
            "Use this verification token to complete sign in: "
            f"{token}\n\nThis token expires in 10 minutes."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return token


def send_username_recovery_email(user):
    send_mail(
        "Your Subscription Intelligence username",
        (
            "We received a request to recover the username for your Subscription Intelligence account.\n\n"
            f"Your username is: {user.username}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_reset_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = request.build_absolute_uri(
        reverse("accounts:reset_password_confirm", kwargs={"uidb64": uid, "token": token})
    )
    send_mail(
        "Reset your Subscription Intelligence password",
        (
            "We received a request to reset the password for your Subscription Intelligence account.\n\n"
            f"Open this password reset link to choose a new password:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_username_change_token_email(user, new_username):
    token = issue_email_token(user.email, purpose=USERNAME_CHANGE_TOKEN_PURPOSE)
    send_mail(
        "Confirm your Subscription Intelligence username change",
        (
            "Use this confirmation token to change your Subscription Intelligence username: "
            f"{token}\n\n"
            f"Requested username: {new_username}\n\n"
            "This token expires in 10 minutes. If you did not request this change, ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return token


def exchange_gmail_oauth_code(code):
    data = urlencode(
        {
            "code": code,
            "client_id": getattr(settings, "GMAIL_OAUTH_CLIENT_ID", ""),
            "client_secret": getattr(settings, "GMAIL_OAUTH_CLIENT_SECRET", ""),
            "redirect_uri": getattr(settings, "GMAIL_OAUTH_REDIRECT_URI", ""),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_gmail_profile(token_payload):
    request = Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class SubscriptionLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True
    authentication_form = SubscriptionAuthenticationForm

    def get_success_url(self):
        return reverse("dashboard")

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        ip_address = get_client_ip(request)
        if is_rate_limited(
            "login",
            username,
            ip_address,
            limit=LOGIN_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            form = self.get_form_class()(request, data=request.POST)
            form.add_error(None, RATE_LIMIT_MESSAGE)
            return self.render_to_response(self.get_context_data(form=form))
        return super().post(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
            return redirect("accounts:verify_token")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        try:
            send_verification_token_email(user)
        except (OSError, SMTPException):
            logger.exception("Failed to send login verification token.")
            form.add_error(
                None,
                "We could not send your verification token. Check the email settings and try again.",
            )
            return self.render_to_response(self.get_context_data(form=form))

        login(self.request, user)
        self.request.session.pop(LEGACY_REACTIVATION_SESSION_KEY, None)
        clear_attempts("login", form.cleaned_data.get("username", ""), get_client_ip(self.request))
        self.request.session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
        messages.success(self.request, "Enter the 6-digit token we sent to your email to finish signing in.")
        return redirect("accounts:verify_token")

    def form_invalid(self, form):
        username = self.request.POST.get("username", "")
        record_attempt(
            "login",
            username,
            get_client_ip(self.request),
            limit=LOGIN_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )
        inactive_user = getattr(form, "inactive_user", None)
        if inactive_user is not None:
            self.request.session[LEGACY_REACTIVATION_SESSION_KEY] = inactive_user.pk
        else:
            self.request.session.pop(LEGACY_REACTIVATION_SESSION_KEY, None)
        return super().form_invalid(form)


def signup_view(request):
    if request.user.is_authenticated:
        if request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
            return redirect("dashboard")
        return redirect("accounts:verify_token")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error("username", "An account with this username already exists.")
        else:
            messages.success(request, "Your account has been created. Sign in to receive your verification token.")
            return redirect("accounts:login")
    return render(request, "registration/signup.html", {"form": form})


def forgot_username_view(request):
    form = AccountRecoveryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        ip_address = get_client_ip(request)
        if is_rate_limited(
            "forgot-username",
            email,
            ip_address,
            limit=RECOVERY_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            form.add_error(None, RATE_LIMIT_MESSAGE)
        else:
            record_attempt(
                "forgot-username",
                email,
                ip_address,
                limit=RECOVERY_RATE_LIMIT,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                form.add_error("email", "No account is associated with this email address.")
            else:
                send_username_recovery_email(user)
                messages.success(request, "Your username has been sent to the email address on the account.")
                return redirect("accounts:login")
    return render(
        request,
        "registration/forgot_username.html",
        {
            "form": form,
        },
    )


def forgot_password_view(request):
    form = AccountRecoveryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        ip_address = get_client_ip(request)
        if is_rate_limited(
            "forgot-password",
            email,
            ip_address,
            limit=RECOVERY_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            form.add_error(None, RATE_LIMIT_MESSAGE)
        else:
            record_attempt(
                "forgot-password",
                email,
                ip_address,
                limit=RECOVERY_RATE_LIMIT,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                form.add_error("email", "No account is associated with this email address.")
            else:
                send_password_reset_email(request, user)
                messages.success(request, "A password reset link has been sent to the email address on the account.")
                return redirect("accounts:login")
    return render(
        request,
        "registration/forgot_password.html",
        {
            "form": form,
        },
    )


def _get_user_from_uid(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        return None
    return User.objects.filter(pk=uid).first()


def _delete_user_sessions(user, keep_session_key=None):
    user_id = str(user.pk)
    for session in Session.objects.all():
        if keep_session_key and session.session_key == keep_session_key:
            continue
        data = session.get_decoded()
        if data.get("_auth_user_id") == user_id:
            session.delete()


def _account_settings_context(request, username_form=None, password_form=None):
    email_connections = EmailConnection.objects.filter(user=request.user)
    active_email_connection = email_connections.filter(status=EmailConnection.STATUS_ACTIVE).first()
    latest_scan = None
    if active_email_connection is not None:
        latest_scan = (
            EmailScanRun.objects.filter(user=request.user, email_connection=active_email_connection)
            .order_by("-created_at", "-id")
            .first()
        )
    scan_preferences, _ = EmailScanPreference.objects.get_or_create(user=request.user)
    privacy_controls = {
        "scan_scope": scan_preferences.scan_scope,
        "retention_period_days": str(scan_preferences.retention_period_days),
        "automatic_scans": scan_preferences.automatic_scans,
    }
    return {
        "username_form": username_form or UsernameChangeRequestForm(user=request.user),
        "password_form": password_form or PasswordChangeForm(user=request.user),
        "email_connections": email_connections,
        "active_email_connection": active_email_connection,
        "latest_gmail_scan": latest_scan,
        "privacy_controls": privacy_controls,
    }


def _automatic_scans_enabled(user):
    return EmailScanPreference.objects.filter(user=user, automatic_scans=True).exists()


def _queue_automatic_gmail_scan(user, connection):
    if _automatic_scans_enabled(user) and connection.status == EmailConnection.STATUS_ACTIVE:
        scan_email_inbox_task(user.id, connection.id)


def _disable_automatic_scans(user):
    EmailScanPreference.objects.update_or_create(
        user=user,
        defaults={"automatic_scans": False},
    )


def _render_account_settings(request, username_form=None, password_form=None):
    return render(
        request,
        "registration/account_settings.html",
        _account_settings_context(request, username_form=username_form, password_form=password_form),
    )


def _confirmation_is_valid(request, expected_text):
    password = request.POST.get("password", "")
    confirmation = request.POST.get("confirmation", "")
    if not request.user.check_password(password):
        messages.error(request, "Enter your current password to continue.")
        return False
    if confirmation != expected_text:
        messages.error(request, f"Type {expected_text} to confirm.")
        return False
    return True


def _account_export_payload(user):
    return {
        "account": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "subscriptions": list(
            Subscription.objects.filter(user=user).values(
                "id",
                "merchant_name",
                "normalized_vendor",
                "amount",
                "currency",
                "cadence",
                "category",
                "next_renewal",
                "status",
                "created_at",
            )
        ),
        "transaction_evidence": list(
            TransactionEvidence.objects.filter(user=user).values(
                "id",
                "provider",
                "account_id",
                "provider_transaction_id",
                "merchant_name",
                "amount",
                "currency",
                "posted_at",
                "created_at",
            )
        ),
        "email_subscription_leads": list(
            EmailSubscriptionLead.objects.filter(user=user).values(
                "id",
                "message_id",
                "sender",
                "subject",
                "merchant_name",
                "received_at",
                "confidence_score",
                "status",
                "created_at",
            )
        ),
    }


def reset_password_confirm_view(request, uidb64, token):
    user = _get_user_from_uid(uidb64)
    token_is_valid = user is not None and default_token_generator.check_token(user, token)
    if not token_is_valid:
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect("accounts:forgot_password")

    form = PasswordResetConfirmForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password"])
        user.save(update_fields=["password"])
        _delete_user_sessions(user)
        messages.success(request, "Your password has been reset. Sign in with your new password.")
        return redirect("accounts:login")

    return render(
        request,
        "registration/reset_password_confirm.html",
        {
            "form": form,
        },
    )


@login_required
def account_settings_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return _render_account_settings(request)


@login_required
def connect_gmail_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    state = secrets.token_urlsafe(32)
    request.session[GMAIL_OAUTH_STATE_SESSION_KEY] = state
    params = {
        "client_id": getattr(settings, "GMAIL_OAUTH_CLIENT_ID", ""),
        "redirect_uri": getattr(settings, "GMAIL_OAUTH_REDIRECT_URI", request.build_absolute_uri(reverse("accounts:gmail_oauth_callback"))),
        "response_type": "code",
        "scope": GMAIL_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@login_required
def gmail_oauth_callback_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    expected_state = request.session.pop(GMAIL_OAUTH_STATE_SESSION_KEY, "")
    if not expected_state or request.GET.get("state") != expected_state:
        messages.error(request, "Email connection could not be verified.")
        return redirect("accounts:account_settings")

    if request.GET.get("error"):
        messages.error(request, "Gmail connection was cancelled.")
        return redirect("accounts:account_settings")

    code = request.GET.get("code")
    if not code:
        messages.error(request, "Gmail did not return an authorization code.")
        return redirect("accounts:account_settings")

    try:
        token_payload = exchange_gmail_oauth_code(code)
        profile_payload = fetch_gmail_profile(token_payload)
    except Exception:
        logger.exception("Failed to complete Gmail OAuth callback.")
        messages.error(request, "Gmail connection failed. Please try again.")
        return redirect("accounts:account_settings")

    scopes = token_payload.get("scope", GMAIL_READONLY_SCOPE).split()
    expires_in = int(token_payload.get("expires_in", 3600))
    email_address = profile_payload.get("emailAddress", "").strip()
    if not email_address:
        messages.error(request, "Gmail did not return a mailbox address.")
        return redirect("accounts:account_settings")

    existing_connection = EmailConnection.objects.filter(
        user=request.user,
        provider=EmailConnection.PROVIDER_GMAIL,
        email_address=email_address,
    ).first()
    refresh_token = token_payload.get("refresh_token") or (
        existing_connection.decrypted_refresh_token() if existing_connection else ""
    )
    connection, _ = EmailConnection.objects.update_or_create(
        user=request.user,
        provider=EmailConnection.PROVIDER_GMAIL,
        email_address=email_address,
        defaults={
            "scopes": scopes,
            "access_token": token_payload["access_token"],
            "refresh_token": refresh_token,
            "token_expires_at": timezone.now() + timedelta(seconds=expires_in),
            "status": EmailConnection.STATUS_ACTIVE,
        },
    )
    _queue_automatic_gmail_scan(request.user, connection)
    messages.success(request, "Gmail connected.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def disconnect_email_connection_view(request, connection_id):
    gate = _require_verified_session(request)
    if gate:
        return gate

    connection = EmailConnection.objects.filter(pk=connection_id, user=request.user).first()
    if connection is None:
        messages.error(request, "Email connection was not found for this account.")
        return redirect("accounts:account_settings")

    connection.status = EmailConnection.STATUS_DISCONNECTED
    connection.access_token = ""
    connection.save(update_fields=["status", "access_token", "updated_at"])
    messages.success(request, "Gmail disconnected.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def resync_gmail_view(request, connection_id):
    gate = _require_verified_session(request)
    if gate:
        return gate

    connection = EmailConnection.objects.filter(
        pk=connection_id,
        user=request.user,
        status=EmailConnection.STATUS_ACTIVE,
    ).first()
    if connection is None:
        raise PermissionDenied("Email connection is not available for this account.")

    scan_email_inbox_task(request.user.id, connection.id)
    messages.success(request, "Gmail re-sync started.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def revoke_gmail_view(request, connection_id):
    gate = _require_verified_session(request)
    if gate:
        return gate

    connection = EmailConnection.objects.filter(pk=connection_id, user=request.user).first()
    if connection is None:
        raise PermissionDenied("Email connection is not available for this account.")

    connection.status = EmailConnection.STATUS_DISCONNECTED
    connection.access_token = ""
    connection.refresh_token = ""
    connection.save(update_fields=["status", "access_token", "refresh_token", "updated_at"])
    _disable_automatic_scans(request.user)
    messages.success(request, "Gmail access revoked.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def logout_other_sessions_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    _delete_user_sessions(request.user, keep_session_key=request.session.session_key)
    messages.success(request, "Other sessions have been logged out.")
    return redirect("accounts:account_settings")


@login_required
def export_account_data_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    return JsonResponse(_account_export_payload(request.user))


@login_required
def export_account_data_for_user_view(request, user_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    if request.user.id != user_id:
        raise PermissionDenied("You cannot export another user's account data.")
    return JsonResponse(_account_export_payload(request.user))


@login_required
@require_POST
def delete_subscription_view(request, subscription_id):
    gate = _require_verified_session(request)
    if gate:
        return gate

    subscription = Subscription.objects.filter(pk=subscription_id, user=request.user).first()
    if subscription is None:
        raise PermissionDenied("You cannot delete another user's subscription.")
    if _confirmation_is_valid(request, "DELETE SUBSCRIPTION"):
        subscription.delete()
        messages.success(request, "Subscription deleted.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def delete_imported_evidence_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    if _confirmation_is_valid(request, "DELETE DATA"):
        TransactionEvidence.objects.filter(user=request.user).delete()
        TransactionImportRun.objects.filter(user=request.user).delete()
        SubscriptionCandidate.objects.filter(user=request.user).delete()
        EmailSubscriptionLead.objects.filter(user=request.user).delete()
        EmailScanRun.objects.filter(user=request.user).delete()
        messages.success(request, "Imported evidence deleted.")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def delete_imported_evidence_for_user_view(request, user_id):
    gate = _require_verified_session(request)
    if gate:
        return gate
    if request.user.id != user_id:
        raise PermissionDenied("You cannot delete another user's imported evidence.")
    return delete_imported_evidence_view(request)


@login_required
@require_POST
def close_account_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    if _confirmation_is_valid(request, "CLOSE ACCOUNT"):
        request.user.is_active = False
        request.user.save(update_fields=["is_active"])
        _delete_user_sessions(request.user)
        logout(request)
        messages.success(request, "Account closed.")
        return redirect("accounts:login")
    return redirect("accounts:account_settings")


@login_required
@require_POST
def update_privacy_controls_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate

    scan_scope = request.POST.get("scan_scope", EmailScanPreference.SCOPE_RECEIPTS_ONLY)
    if scan_scope not in dict(EmailScanPreference.SCOPE_CHOICES):
        scan_scope = EmailScanPreference.SCOPE_RECEIPTS_ONLY
    try:
        retention_period_days = int(request.POST.get("retention_period_days", "180"))
    except ValueError:
        retention_period_days = 180
    if retention_period_days not in {30, 90, 180}:
        retention_period_days = 180

    EmailScanPreference.objects.update_or_create(
        user=request.user,
        defaults={
            "scan_scope": scan_scope,
            "retention_period_days": retention_period_days,
            "automatic_scans": request.POST.get("automatic_scans") == "on",
        },
    )
    messages.success(request, "Privacy controls saved.")
    return redirect("accounts:account_settings")


@login_required
def change_username_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    form = UsernameChangeRequestForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        new_username = form.cleaned_data["new_username"]
        request.session[PENDING_USERNAME_SESSION_KEY] = new_username
        send_username_change_token_email(request.user, new_username)
        messages.success(request, "A confirmation token has been sent to your account email.")
        return redirect("accounts:confirm_username_change")
    if request.method == "POST" and request.headers.get("HX-Request") == "true":
        return _render_account_settings(request, username_form=form)
    return render(
        request,
        "registration/change_username.html",
        {
            "form": form,
        },
    )


@login_required
def confirm_username_change_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    pending_username = request.session.get(PENDING_USERNAME_SESSION_KEY)
    if not pending_username:
        messages.error(request, "Start a username change before entering a confirmation token.")
        return redirect("accounts:change_username")

    form = UsernameChangeTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if User.objects.filter(username=pending_username).exclude(pk=request.user.pk).exists():
            request.session.pop(PENDING_USERNAME_SESSION_KEY, None)
            clear_email_token(request.user.email, purpose=USERNAME_CHANGE_TOKEN_PURPOSE)
            messages.error(request, "That username is no longer available.")
            return redirect("accounts:change_username")
        if verify_email_token(
            request.user.email,
            form.cleaned_data["token"],
            purpose=USERNAME_CHANGE_TOKEN_PURPOSE,
        ):
            request.user.username = pending_username
            request.user.save(update_fields=["username"])
            request.session.pop(PENDING_USERNAME_SESSION_KEY, None)
            clear_email_token(request.user.email, purpose=USERNAME_CHANGE_TOKEN_PURPOSE)
            messages.success(request, "Your username has been updated.")
            return redirect("dashboard")
        form.add_error("token", "The confirmation token is invalid or has expired.")

    return render(
        request,
        "registration/confirm_username_change.html",
        {
            "form": form,
            "pending_username": pending_username,
        },
    )


@login_required
def change_password_view(request):
    gate = _require_verified_session(request)
    if gate:
        return gate
    form = PasswordChangeForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["new_password"])
        request.user.save(update_fields=["password"])
        _delete_user_sessions(request.user)
        messages.success(request, "Your password has been updated. Sign in with your new password.")
        return redirect("accounts:login")
    if request.method == "POST" and request.headers.get("HX-Request") == "true":
        return _render_account_settings(request, password_form=form)
    return render(
        request,
        "registration/change_password.html",
        {
            "form": form,
        },
    )


def verify_token_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    if request.session.get(LOGIN_TOKEN_VERIFIED_SESSION_KEY):
        return redirect("dashboard")

    ip_address = get_client_ip(request)
    email = request.user.email
    if request.method == "POST":
        form = LoginTokenVerificationForm(request.POST)
        resend_form = ResendTokenForm()
        if is_rate_limited(
            "login-token-verify",
            email,
            ip_address,
            limit=TOKEN_VERIFY_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            form.add_error("token", RATE_LIMIT_MESSAGE)
        elif form.is_valid():
            token = form.cleaned_data["token"]
            if verify_email_token(email, token):
                request.session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
                clear_attempts("login-token-verify", email, ip_address)
                clear_email_token(email)
                messages.success(request, "Token verified. Welcome back.")
                return redirect("dashboard")
            record_attempt(
                "login-token-verify",
                email,
                ip_address,
                limit=TOKEN_VERIFY_RATE_LIMIT,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )
            form.add_error("token", "The verification token is invalid or has expired.")
    else:
        form = LoginTokenVerificationForm()
        resend_form = ResendTokenForm()

    return render(
        request,
        "registration/verify_token.html",
        {
            "form": form,
            "resend_form": resend_form,
        },
    )


def resend_token_view(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    ip_address = get_client_ip(request)
    email = request.user.email
    if request.method == "POST":
        if is_rate_limited(
            "login-token-resend",
            email,
            ip_address,
            limit=TOKEN_RESEND_RATE_LIMIT,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        ):
            messages.error(request, RATE_LIMIT_MESSAGE)
        else:
            record_attempt(
                "login-token-resend",
                email,
                ip_address,
                limit=TOKEN_RESEND_RATE_LIMIT,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )
            try:
                send_verification_token_email(request.user)
            except (OSError, SMTPException):
                logger.exception("Failed to resend login verification token.")
                messages.error(request, "We could not send a new verification token. Check the email settings and try again.")
            else:
                request.session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
                messages.success(request, "A new verification token has been sent.")
        return redirect("accounts:verify_token")

    return render(
        request,
        "registration/verify_token.html",
        {
            "form": LoginTokenVerificationForm(),
            "resend_form": ResendTokenForm(),
        },
    )


def activate_view(request, uidb64, token):
    messages.error(request, "Email links are no longer used. Sign in and enter your verification token instead.")
    return redirect("accounts:login")


def cancel_token_verification_view(request):
    request.session.pop(LOGIN_TOKEN_VERIFIED_SESSION_KEY, None)
    request.session.pop(LEGACY_REACTIVATION_SESSION_KEY, None)
    if request.user.is_authenticated:
        logout(request)
    messages.info(request, "Signed out of the pending verification session. You can sign in with a different account.")
    return redirect("accounts:login")


def reactivate_legacy_account_view(request):
    if request.method != "POST":
        return redirect("accounts:login")

    user_id = request.session.get(LEGACY_REACTIVATION_SESSION_KEY)
    if not user_id:
        messages.error(request, "We could not find a legacy account to reactivate.")
        return redirect("accounts:login")

    user = User.objects.filter(pk=user_id, is_active=False).first()
    request.session.pop(LEGACY_REACTIVATION_SESSION_KEY, None)

    if user is None:
        messages.error(request, "That account is already active or no longer available for recovery.")
        return redirect("accounts:login")

    user.is_active = True
    user.save(update_fields=["is_active"])
    messages.success(request, "Legacy account reactivated. Sign in again to receive your verification token.")
    return redirect("accounts:login")
