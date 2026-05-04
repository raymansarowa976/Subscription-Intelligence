from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sessions.models import Session

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
LOGIN_TOKEN_VERIFIED_SESSION_KEY = "login_token_verified"
LEGACY_REACTIVATION_SESSION_KEY = "legacy_reactivation_user_id"
USERNAME_CHANGE_TOKEN_PURPOSE = "username-change"
PENDING_USERNAME_SESSION_KEY = "pending_username_change"
LOGIN_RATE_LIMIT = 5
RECOVERY_RATE_LIMIT = 5
TOKEN_VERIFY_RATE_LIMIT = 5
TOKEN_RESEND_RATE_LIMIT = 3
RATE_LIMIT_WINDOW_SECONDS = 900


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
        response = super().form_valid(form)
        self.request.session.pop(LEGACY_REACTIVATION_SESSION_KEY, None)
        clear_attempts("login", form.cleaned_data.get("username", ""), get_client_ip(self.request))
        self.request.session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
        send_verification_token_email(self.request.user)
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


def _delete_user_sessions(user):
    user_id = str(user.pk)
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get("_auth_user_id") == user_id:
            session.delete()


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
        update_session_auth_hash(request, request.user)
        messages.success(request, "Your password has been updated.")
        return redirect("dashboard")
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
            send_verification_token_email(request.user)
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
