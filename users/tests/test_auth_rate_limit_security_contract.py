from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from users.auth.rate_limiter import RATE_LIMIT_MESSAGE
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class AuthenticationRateLimitSecurityContractTests(TestCase):
    def setUp(self):
        cache.clear()
        self.login_url = reverse("accounts:login")
        self.verify_url = reverse("accounts:verify_token")
        self.resend_url = reverse("accounts:resend_token")
        self.forgot_username_url = reverse("accounts:forgot_username")
        self.forgot_password_url = reverse("accounts:forgot_password")

    def _verified_user(self, username="rateuser", email="rateuser@gmail.com"):
        return User.objects.create_user(
            username=username,
            email=email,
            password="Complex123!",
            is_active=True,
        )

    def _login_pending_token(self, client, user):
        client.force_login(user)
        session = client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
        session.save()

    def test_login_rate_limit_blocks_normalized_identifier_across_ips(self):
        user = self._verified_user(email="identifierlimit@gmail.com")

        for index in range(5):
            response = self.client.post(
                self.login_url,
                {"username": "  IDENTIFIERLIMIT@GMAIL.COM  ", "password": "Wrong123!"},
                REMOTE_ADDR=f"10.0.0.{index + 1}",
            )
            self.assertContains(response, "Please enter a correct username and password.")

        limited_response = self.client.post(
            self.login_url,
            {"username": user.email, "password": "Complex123!"},
            REMOTE_ADDR="10.0.0.99",
        )

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_rate_limit_blocks_ip_across_different_identifiers(self):
        user = self._verified_user(email="iplimit@gmail.com")

        for index in range(5):
            response = self.client.post(
                self.login_url,
                {"username": f"unknown-{index}@gmail.com", "password": "Wrong123!"},
                REMOTE_ADDR="10.0.1.10",
            )
            self.assertContains(response, "Please enter a correct username and password.")

        limited_response = self.client.post(
            self.login_url,
            {"username": user.email, "password": "Complex123!"},
            REMOTE_ADDR="10.0.1.10",
        )

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)
        self.assertEqual(len(mail.outbox), 0)

    def test_recovery_rate_limit_blocks_normalized_identifier_across_ips(self):
        for url in [self.forgot_username_url, self.forgot_password_url]:
            with self.subTest(url=url):
                cache.clear()
                for index in range(5):
                    response = self.client.post(
                        url,
                        {"email": "  MISSING-RATE@GMAIL.COM  "},
                        REMOTE_ADDR=f"10.0.2.{index + 1}",
                    )
                    self.assertContains(response, "No account is associated with this email address.")

                limited_response = self.client.post(
                    url,
                    {"email": "missing-rate@gmail.com"},
                    REMOTE_ADDR="10.0.2.99",
                )

                self.assertEqual(limited_response.status_code, 200)
                self.assertContains(limited_response, RATE_LIMIT_MESSAGE)

    def test_recovery_rate_limit_blocks_ip_across_different_identifiers(self):
        for url in [self.forgot_username_url, self.forgot_password_url]:
            with self.subTest(url=url):
                cache.clear()
                for index in range(5):
                    response = self.client.post(
                        url,
                        {"email": f"missing-{index}@gmail.com"},
                        REMOTE_ADDR="10.0.3.10",
                    )
                    self.assertContains(response, "No account is associated with this email address.")

                limited_response = self.client.post(
                    url,
                    {"email": "another-missing@gmail.com"},
                    REMOTE_ADDR="10.0.3.10",
                )

                self.assertEqual(limited_response.status_code, 200)
                self.assertContains(limited_response, RATE_LIMIT_MESSAGE)

    def test_login_token_verification_rate_limit_blocks_identifier_across_ips(self):
        user = self._verified_user(email="verifyidentifier@gmail.com")
        client = Client()
        self._login_pending_token(client, user)

        for index in range(5):
            response = client.post(
                self.verify_url,
                {"token": "999999"},
                REMOTE_ADDR=f"10.0.4.{index + 1}",
            )
            self.assertContains(response, "The verification token is invalid or has expired.")

        limited_response = client.post(
            self.verify_url,
            {"token": "999999"},
            REMOTE_ADDR="10.0.4.99",
        )

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)

    def test_login_token_verification_rate_limit_blocks_ip_across_users(self):
        for index in range(5):
            user = self._verified_user(
                username=f"verifyip{index}",
                email=f"verifyip{index}@gmail.com",
            )
            client = Client()
            self._login_pending_token(client, user)
            response = client.post(
                self.verify_url,
                {"token": "999999"},
                REMOTE_ADDR="10.0.5.10",
            )
            self.assertContains(response, "The verification token is invalid or has expired.")

        limited_user = self._verified_user(username="verifyiplimit", email="verifyiplimit@gmail.com")
        limited_client = Client()
        self._login_pending_token(limited_client, limited_user)
        limited_response = limited_client.post(
            self.verify_url,
            {"token": "999999"},
            REMOTE_ADDR="10.0.5.10",
        )

        self.assertEqual(limited_response.status_code, 200)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)

    def test_token_resend_rate_limit_blocks_identifier_across_ips(self):
        user = self._verified_user(email="resendidentifier@gmail.com")
        client = Client()
        self._login_pending_token(client, user)

        for index in range(3):
            response = client.post(
                self.resend_url,
                follow=True,
                REMOTE_ADDR=f"10.0.6.{index + 1}",
            )
            self.assertContains(response, "A new verification token has been sent.")

        limited_response = client.post(
            self.resend_url,
            follow=True,
            REMOTE_ADDR="10.0.6.99",
        )

        self.assertRedirects(limited_response, self.verify_url)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)

    def test_token_resend_rate_limit_blocks_ip_across_users(self):
        for index in range(3):
            user = self._verified_user(
                username=f"resendip{index}",
                email=f"resendip{index}@gmail.com",
            )
            client = Client()
            self._login_pending_token(client, user)
            response = client.post(
                self.resend_url,
                follow=True,
                REMOTE_ADDR="10.0.7.10",
            )
            self.assertContains(response, "A new verification token has been sent.")

        limited_user = self._verified_user(username="resendiplimit", email="resendiplimit@gmail.com")
        limited_client = Client()
        self._login_pending_token(limited_client, limited_user)
        limited_response = limited_client.post(
            self.resend_url,
            follow=True,
            REMOTE_ADDR="10.0.7.10",
        )

        self.assertRedirects(limited_response, self.verify_url)
        self.assertContains(limited_response, RATE_LIMIT_MESSAGE)
