from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse
from smtplib import SMTPAuthenticationError
from unittest.mock import patch
import re


User = get_user_model()


class FrontendIntegrationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.signup_url = reverse("accounts:signup")
        self.login_url = reverse("accounts:login")
        self.verify_url = reverse("accounts:verify_token")
        self.resend_url = reverse("accounts:resend_token")
        self.forgot_username_url = reverse("accounts:forgot_username")
        self.forgot_password_url = reverse("accounts:forgot_password")
        self.account_settings_url = reverse("accounts:account_settings")
        self.change_username_url = reverse("accounts:change_username")
        self.confirm_username_change_url = reverse("accounts:confirm_username_change")
        self.change_password_url = reverse("accounts:change_password")
        self.home_url = reverse("home")
        self.dashboard_url = reverse("dashboard")
        self.valid_signup = {
            "first_name": "Taylor",
            "last_name": "Jordan",
            "username": "frontenduser",
            "email": "frontend@gmail.com",
            "password": "Complex123!",
            "confirm_password": "Complex123!",
        }

    def test_signup_page_renders_professional_ui(self):
        response = self.client.get(self.signup_url)

        self.assertContains(response, "Subscription Intelligence")
        self.assertContains(response, 'rel="icon"', html=False)
        self.assertContains(response, "images/favicon.svg")
        self.assertContains(response, "css/tailwind.css")
        self.assertNotContains(response, "cdn.tailwindcss.com")
        self.assertNotContains(response, "tailwind.config")
        self.assertContains(response, "Create your account")
        self.assertContains(response, 'name="first_name"', html=False)
        self.assertContains(response, 'name="last_name"', html=False)
        self.assertContains(response, 'name="username"', html=False)
        self.assertContains(response, 'name="email"', html=False)
        self.assertContains(response, 'name="password"', html=False)
        self.assertContains(response, 'name="confirm_password"', html=False)
        self.assertContains(response, 'data-password-toggle="id_password"', html=False)
        self.assertContains(response, 'data-password-toggle="id_confirm_password"', html=False)
        self.assertContains(response, 'aria-label="Show password"', html=False)
        self.assertContains(response, 'aria-label="Show confirm password"', html=False)
        self.assertContains(response, "supported provider like gmail.com or outlook.com")
        self.assertContains(response, "Password strength")
        self.assertContains(response, 'id="confirm-password-status"', html=False)
        self.assertContains(response, "At least 1 uppercase letter")
        self.assertContains(response, "signup.js?v=2")

    def test_signup_rejects_mismatched_passwords_with_visible_error(self):
        payload = self.valid_signup.copy()
        payload["confirm_password"] = "Different123!"

        response = self.client.post(self.signup_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match.")
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())

    def test_signup_rejects_invalid_name_characters(self):
        payload = self.valid_signup.copy()
        payload["first_name"] = "T4ylor"
        payload["last_name"] = "Jordan!"

        response = self.client.post(self.signup_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use letters only with no numbers or special characters.", count=2)
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())

    def test_signup_rejects_unsupported_email_domains(self):
        payload = self.valid_signup.copy()
        payload["email"] = "frontend@company.org"

        response = self.client.post(self.signup_url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Use a valid email from a supported provider like gmail.com, hotmail.com, or outlook.com.",
        )
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())

    def test_signup_redirects_to_login_with_success_message(self):
        response = self.client.post(self.signup_url, self.valid_signup, follow=True)

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, "Your account has been created. Sign in to receive your verification token.")
        self.assertContains(response, "Welcome back")

    def test_verify_token_page_renders_resend_option(self):
        user = User.objects.create_user(
            username="verifyuser",
            email="verify@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)

        response = self.client.get(self.verify_url)

        self.assertContains(response, "Verify your login")
        self.assertContains(response, 'name="token"', html=False)
        self.assertContains(response, "Resend token")
        self.assertNotContains(response, "Development token")

    def test_verify_token_with_valid_code_activates_user(self):
        user = User.objects.create_user(
            username="tokenuser",
            email="frontend@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
        )
        token = re.search(r"(\d{6})", mail.outbox[0].body).group(1)

        response = self.client.post(
            self.verify_url,
            {"token": token},
            follow=True,
        )

        self.assertRedirects(response, self.dashboard_url)
        self.assertContains(response, "Dashboard")

    def test_resend_token_sends_fresh_code(self):
        user = User.objects.create_user(
            username="resenduser",
            email="frontend@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
        )

        response = self.client.post(
            self.resend_url,
            follow=True,
        )

        self.assertRedirects(response, self.verify_url)
        self.assertContains(response, "A new verification token has been sent.")
        self.assertEqual(len(mail.outbox), 2)

    def test_login_page_renders_and_valid_credentials_require_token_before_dashboard(self):
        user = User.objects.create_user(
            username="loginuser",
            email="login@gmail.com",
            password="Complex123!",
            is_active=True,
        )

        response = self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
            follow=True,
        )

        self.assertRedirects(response, self.verify_url)
        self.assertContains(response, "Enter the 6-digit token we sent to your email to finish signing in.")
        self.assertContains(response, "Verify your login")

    def test_login_email_delivery_failure_returns_visible_error(self):
        user = User.objects.create_user(
            username="mailfail",
            email="mailfail@gmail.com",
            password="Complex123!",
            is_active=True,
        )

        with patch(
            "users.auth.views.send_verification_token_email",
            side_effect=SMTPAuthenticationError(535, b"Bad credentials"),
        ), patch("users.auth.views.logger.exception"):
            response = self.client.post(
                self.login_url,
                {"username": user.username, "password": "Complex123!"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We could not send your verification token.")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_page_links_to_account_recovery(self):
        response = self.client.get(self.login_url)

        self.assertContains(response, 'data-password-toggle="id_password"', html=False)
        self.assertContains(response, 'aria-label="Show password"', html=False)
        self.assertNotContains(response, 'hx-boost="true"', html=False)
        self.assertContains(response, "password_visibility.js")
        self.assertContains(response, "Forgot username?")
        self.assertContains(response, self.forgot_username_url)
        self.assertContains(response, "Forgot password?")
        self.assertContains(response, self.forgot_password_url)

    def test_login_accepts_valid_csrf_token_when_csrf_checks_are_enforced(self):
        user = User.objects.create_user(
            username="csrfvalid",
            email="csrfvalid@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        login_response = csrf_client.get(self.login_url)
        token = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            login_response.content.decode(),
        ).group(1)

        response = csrf_client.post(
            self.login_url,
            {
                "username": user.username,
                "password": "Complex123!",
                "csrfmiddlewaretoken": token,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.verify_url)

    def test_login_csrf_failure_returns_recoverable_login_page(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get(self.login_url)

        response = csrf_client.post(
            self.login_url,
            {
                "username": "anyone",
                "password": "Complex123!",
                "csrfmiddlewaretoken": "a" * 64,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your sign-in session expired. Please try again.")
        self.assertContains(response, "Welcome back")

    def test_recovery_pages_render(self):
        username_response = self.client.get(self.forgot_username_url)
        password_response = self.client.get(self.forgot_password_url)

        self.assertContains(username_response, "Forgot username")
        self.assertContains(username_response, 'name="email"', html=False)
        self.assertContains(username_response, "Email my username")
        self.assertContains(password_response, "Forgot password")
        self.assertContains(password_response, 'name="email"', html=False)
        self.assertContains(password_response, "Send reset link")

    def test_landing_page_renders_for_anonymous_users(self):
        response = self.client.get(self.home_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find the subscriptions hiding in your inbox")
        self.assertContains(response, "Create account")
        self.assertContains(response, self.signup_url)
        self.assertContains(response, "Sign in")
        self.assertContains(response, self.login_url)
        self.assertContains(response, "Review before tracking")
        self.assertContains(response, "css/tailwind.css")
        self.assertNotContains(response, "cdn.tailwindcss.com")

    def test_landing_page_shows_dashboard_link_for_authenticated_users(self):
        user = User.objects.create_user(
            username="landinguser",
            email="landinguser@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        response = self.client.get(self.home_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open dashboard")
        self.assertContains(response, self.dashboard_url)

    def test_landing_page_mobile_desktop_visual_smoke_guards(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "md:grid-cols-3")
        self.assertContains(response, "lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]")
        self.assertContains(response, "overflow-hidden")
        self.assertContains(response, "max-w-[18rem]")
        self.assertContains(response, "w-full")
        self.assertContains(response, "sm:w-auto")
        self.assertContains(response, "min-h-[52vh]")
        self.assertLess(content.index("Find the subscriptions hiding in your inbox"), content.index("Receipts become structured clues"))
        self.assertLess(content.index("Turn subscription guesswork into a review queue"), content.index("Create account", content.index("Turn subscription guesswork into a review queue")))

    def test_visual_qa_pass_covers_major_auth_and_subscription_pages(self):
        auth_pages = [
            self.signup_url,
            self.login_url,
            self.forgot_username_url,
            self.forgot_password_url,
        ]
        for url in auth_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "css/tailwind.css")
                self.assertContains(response, "min-h-screen")
                self.assertContains(response, "max-w-7xl")
                self.assertNotContains(response, "cdn.tailwindcss.com")

        user = User.objects.create_user(
            username="visualqa",
            email="visualqa@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        subscription_pages = [
            self.dashboard_url,
            reverse("transactions:candidates"),
            reverse("transactions:add_subscription"),
        ]
        for url in subscription_pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "css/tailwind.css")
                self.assertContains(response, "right-sidebar-toggle")
                self.assertContains(response, "max-w-7xl")
                self.assertContains(response, "rounded-[")
                self.assertNotContains(response, "cdn.tailwindcss.com")

    def test_password_reset_confirm_page_renders(self):
        user = User.objects.create_user(
            username="resetrender",
            email="resetrender@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.post(self.forgot_password_url, {"email": user.email})
        reset_path = re.search(r"http://testserver(/[^\s]+)", mail.outbox[0].body).group(1)

        response = self.client.get(reset_path)

        self.assertContains(response, "Set new password")
        self.assertContains(response, 'name="new_password"', html=False)
        self.assertContains(response, 'name="confirm_password"', html=False)
        self.assertContains(response, 'data-password-toggle="id_new_password"', html=False)
        self.assertContains(response, 'data-password-toggle="id_confirm_password"', html=False)
        self.assertContains(response, "Reset password")

    def test_login_invalid_credentials_message_states_case_sensitivity(self):
        user = User.objects.create_user(
            username="CaseUser",
            email="caseuser@gmail.com",
            password="Complex123!",
            is_active=True,
        )

        response = self.client.post(
            self.login_url,
            {"username": user.username.lower(), "password": "complex123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a correct username and password. Both fields are case-sensitive.",
        )

    def test_login_inactive_account_shows_inactive_message(self):
        user = User.objects.create_user(
            username="inactiveuser",
            email="inactive@gmail.com",
            password="Complex123!",
            is_active=False,
        )

        response = self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This account is inactive.")
        self.assertContains(response, "Reactivate account")

    def test_legacy_account_can_be_reactivated_after_valid_inactive_login(self):
        user = User.objects.create_user(
            username="legacyuser",
            email="legacy@gmail.com",
            password="Complex123!",
            is_active=False,
        )

        self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
        )
        response = self.client.post(reverse("accounts:reactivate_account"), follow=True)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertRedirects(response, self.login_url)
        self.assertContains(response, "Legacy account reactivated. Sign in again to receive your verification token.")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(self.dashboard_url)

        expected = f"{self.login_url}?next={self.dashboard_url}"
        self.assertRedirects(response, expected)

    def test_dashboard_requires_verified_login_token(self):
        user = User.objects.create_user(
            username="pendingtoken",
            email="pending@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = False
        session.save()

        response = self.client.get(self.dashboard_url)

        self.assertRedirects(response, self.verify_url)

    def test_dashboard_renders_hideable_sidebar_navigation(self):
        user = User.objects.create_user(
            username="settingslink",
            email="settingslink@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        response = self.client.get(self.dashboard_url)

        self.assertContains(response, 'id="right-sidebar-toggle"', html=False)
        self.assertContains(response, 'data-scroll-header', html=False)
        self.assertContains(response, "scroll_header.js?v=2")
        self.assertContains(response, 'aria-label="Open navigation sidebar"', html=False)
        self.assertContains(response, "Overview and insights")
        self.assertContains(response, "Analytics and reports")
        self.assertContains(response, "Gmail integrations")
        self.assertContains(response, "Data sources")
        self.assertContains(response, self.account_settings_url)
        self.assertNotContains(response, "Profile and username management")

    def test_account_settings_page_links_to_account_change_pages(self):
        user = User.objects.create_user(
            username="settingspage",
            email="settingspage@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        response = self.client.get(self.account_settings_url)

        self.assertContains(response, "Account settings")
        self.assertContains(response, "Change username")
        self.assertContains(response, self.change_username_url)
        self.assertContains(response, "Change password")
        self.assertContains(response, self.change_password_url)

    def test_account_change_pages_render_for_verified_user(self):
        user = User.objects.create_user(
            username="settingsuser",
            email="settings@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        username_response = self.client.get(self.change_username_url)
        password_response = self.client.get(self.change_password_url)

        self.assertContains(username_response, 'name="new_username"', html=False)
        self.assertContains(username_response, 'name="confirm_username"', html=False)
        self.assertContains(username_response, 'name="current_password"', html=False)
        self.assertContains(username_response, 'data-password-toggle="id_current_password"', html=False)
        self.assertContains(username_response, 'aria-label="Show current password"', html=False)
        self.assertContains(username_response, "password_visibility.js")
        self.assertContains(password_response, 'name="old_password"', html=False)
        self.assertContains(password_response, 'name="new_password"', html=False)
        self.assertContains(password_response, 'name="confirm_password"', html=False)
        self.assertContains(password_response, 'data-password-toggle="id_old_password"', html=False)
        self.assertContains(password_response, 'data-password-toggle="id_new_password"', html=False)
        self.assertContains(password_response, 'data-password-toggle="id_confirm_password"', html=False)
        self.assertContains(password_response, 'aria-label="Show current password"', html=False)
        self.assertContains(password_response, 'aria-label="Show new password"', html=False)
        self.assertContains(password_response, 'aria-label="Show confirm new password"', html=False)
        self.assertContains(password_response, 'id="change-password-match-status"', html=False)
        self.assertContains(password_response, "password_change.js?v=2")

    def test_username_confirmation_page_renders_after_token_request(self):
        user = User.objects.create_user(
            username="confirmrender",
            email="confirmrender@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        response = self.client.post(
            self.change_username_url,
            {
                "new_username": "confirmedrender",
                "confirm_username": "confirmedrender",
                "current_password": "Complex123!",
            },
            follow=True,
        )

        self.assertRedirects(response, self.confirm_username_change_url)
        self.assertContains(response, "Confirm username change")
        self.assertContains(response, "Pending username")
        self.assertContains(response, "confirmedrender")
        self.assertContains(response, 'name="token"', html=False)
        self.assertContains(response, "Confirm username change")
        self.assertEqual(len(mail.outbox), 1)

    def test_account_change_pages_require_verified_login_token(self):
        user = User.objects.create_user(
            username="settingspending",
            email="settingspending@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = False
        session.save()

        protected_urls = [
            self.change_username_url,
            self.confirm_username_change_url,
            self.change_password_url,
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, self.verify_url)

    def test_username_confirmation_redirects_without_pending_username(self):
        user = User.objects.create_user(
            username="nopending",
            email="nopending@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        response = self.client.get(self.confirm_username_change_url, follow=True)

        self.assertRedirects(response, self.change_username_url)
        self.assertContains(response, "Start a username change before entering a confirmation token.")

    def test_cancel_verification_returns_user_to_login(self):
        user = User.objects.create_user(
            username="canceluser",
            email="cancel@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.post(
            self.login_url,
            {"username": user.username, "password": "Complex123!"},
        )

        response = self.client.get(reverse("accounts:cancel_verification"), follow=True)

        self.assertRedirects(response, self.login_url)
        self.assertContains(response, "Signed out of the pending verification session.")
        self.assertContains(response, "Welcome back")
