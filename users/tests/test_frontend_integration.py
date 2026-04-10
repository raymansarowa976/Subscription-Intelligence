from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class FrontendIntegrationTest(TestCase):
    def setUp(self):
        self.signup_url = reverse("accounts:signup")
        self.login_url = reverse("accounts:login")
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
        self.assertContains(response, "Check your inbox to verify your email before signing in.")
        self.assertContains(response, "Welcome back")

    def test_login_page_renders_and_valid_credentials_reach_dashboard(self):
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

        self.assertRedirects(response, self.dashboard_url)
        self.assertContains(response, "Workspace overview")
        self.assertContains(response, f"Welcome back, {user.username}")

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

    def test_dashboard_requires_authentication(self):
        response = self.client.get(self.dashboard_url)

        expected = f"{self.login_url}?next={self.dashboard_url}"
        self.assertRedirects(response, expected)
