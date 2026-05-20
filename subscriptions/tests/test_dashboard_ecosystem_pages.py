from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import EmailConnection, EmailScanRun, Subscription, SubscriptionCandidate
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class DashboardEcosystemPagesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ecosystemuser",
            email="ecosystem@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()

    def _connection(self):
        return EmailConnection.objects.create(
            user=self.user,
            provider=EmailConnection.PROVIDER_GMAIL,
            email_address="ecosystem@gmail.com",
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            access_token="access-token",
            refresh_token="refresh-token",
            token_expires_at=timezone.now() + timedelta(hours=1),
            status=EmailConnection.STATUS_ACTIVE,
        )

    def test_gmail_integrations_page_guides_unconnected_users_before_scanning(self):
        response = self.client.get("/dashboard/gmail/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect Gmail")
        self.assertContains(response, "Connect Gmail to unlock inbox scanning")
        self.assertContains(response, reverse("accounts:connect_gmail"))
        self.assertNotContains(response, "Scan inbox now")
        self.assertNotContains(response, reverse("scan_inbox"))

    def test_gmail_integrations_page_exposes_scan_controls_after_connection(self):
        connection = self._connection()

        response = self.client.get("/dashboard/gmail/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ecosystem@gmail.com")
        self.assertContains(response, "Scan inbox now")
        self.assertContains(response, reverse("scan_inbox"))
        self.assertContains(response, f'name="email_connection_id" value="{connection.id}"', html=False)
        self.assertContains(response, "Gmail re-sync")
        self.assertContains(response, "Disconnect")
        self.assertContains(response, "Revoke access")

    def test_analytics_page_owns_reports_and_dashboard_charts(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
            next_renewal=date.today() + timedelta(days=3),
        )

        response = self.client.get("/dashboard/analytics/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Analytics and reports")
        self.assertContains(response, "Category mix")
        self.assertContains(response, "6-month spend curve")
        self.assertContains(response, "categoryChart")
        self.assertContains(response, "trendChart")
        self.assertContains(response, "cdn.jsdelivr.net/npm/chart.js")

    def test_data_sources_page_owns_mailbox_health_and_connection_logs(self):
        connection = self._connection()
        EmailScanRun.objects.create(
            user=self.user,
            email_connection=connection,
            provider=EmailConnection.PROVIDER_GMAIL,
            mailbox="ecosystem@gmail.com",
            status=EmailScanRun.STATUS_SUCCEEDED,
            scanned_message_count=30,
            matched_message_count=4,
        )
        EmailScanRun.objects.create(
            user=self.user,
            email_connection=connection,
            provider=EmailConnection.PROVIDER_GMAIL,
            mailbox="ecosystem@gmail.com",
            status=EmailScanRun.STATUS_FAILED,
            scanned_message_count=2,
            matched_message_count=0,
            error_details={"errors": ["Token expired"]},
        )

        response = self.client.get("/dashboard/data-sources/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data sources")
        self.assertContains(response, "Mailbox health")
        self.assertContains(response, "Connection logs")
        self.assertContains(response, "ecosystem@gmail.com")
        self.assertContains(response, "Succeeded")
        self.assertContains(response, "Failed")
        self.assertContains(response, "30 processed")
        self.assertContains(response, "Token expired")

    def test_ecosystem_pages_require_verified_login_token(self):
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
        session.save()

        for url in ["/dashboard/gmail/", "/dashboard/analytics/", "/dashboard/data-sources/"]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("accounts:verify_token"))

    def test_data_sources_excludes_review_and_analytics_concerns(self):
        SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
        )

        response = self.client.get("/dashboard/data-sources/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review Pending Items")
        self.assertNotContains(response, "6-month spend curve")
