from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
import re


User = get_user_model()


class FrontendIntegrationTest(TestCase):
    def setUp(self):
        self.signup_url = reverse("accounts:signup")
        self.login_url = reverse("accounts:login")
        self.verify_url = reverse("accounts:verify_token")
        self.resend_url = reverse("accounts:resend_token")
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
        self.assertContains(response, "Create your account")
        self.assertContains(response, 'name="first_name"', html=False)
        self.assertContains(response, 'name="last_name"', html=False)
        self.assertContains(response, 'name="username"', html=False)
        self.assertContains(response, 'name="email"', html=False)
        self.assertContains(response, 'name="password"', html=False)
        self.assertContains(response, 'name="confirm_password"', html=False)
        self.assertContains(response, "supported provider like gmail.com or outlook.com")
        self.assertContains(response, "Password strength")
        self.assertContains(response, 'id="confirm-password-status"', html=False)
        self.assertContains(response, "At least 1 uppercase letter")

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
        self.assertContains(response, "Subscription workspace")

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
