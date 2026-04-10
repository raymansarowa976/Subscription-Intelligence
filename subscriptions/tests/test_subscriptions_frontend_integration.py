from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import Subscription, SubscriptionCandidate, TransactionEvidence


User = get_user_model()


class SubscriptionsFrontendIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="productuser",
            email="product@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        self.dashboard_url = reverse("dashboard")
        self.candidates_url = reverse("transactions:candidates")
        self.add_subscription_url = reverse("transactions:add_subscription")

    def test_dashboard_renders_metrics_workspace_and_empty_states(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription workspace")
        self.assertContains(response, "Total monthly spend")
        self.assertContains(response, "Upcoming renewals")
        self.assertContains(response, "Annual run-rate")
        self.assertContains(response, "Subscriptions")
        self.assertContains(response, "Log out")
        self.assertContains(response, "Quick add subscription")
        self.assertContains(response, "Recently found")
        self.assertContains(response, "Security check")
        self.assertContains(response, "No subscriptions confirmed yet.")
        self.assertContains(response, "No new receipts are waiting for review.")

    def test_dashboard_displays_confirmed_subscriptions_and_personalized_metrics(self):
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
        Subscription.objects.create(
            user=self.user,
            merchant_name="Adobe",
            normalized_vendor="adobe",
            amount="120.00",
            currency="USD",
            cadence="yearly",
            category=Subscription.CATEGORY_SOFTWARE,
            next_renewal=date.today() + timedelta(days=30),
        )
        TransactionEvidence.objects.create(
            user=self.user,
            provider="plaid",
            account_id="acct_dashboard",
            provider_transaction_id="txn_sync_001",
            merchant_name="Netflix",
            description="NETFLIX.COM",
            amount="15.49",
            currency="USD",
            posted_at=date.today(),
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello, productuser, you have 1 renewal this week.")
        self.assertContains(response, "$25.49")
        self.assertContains(response, "$305.88")
        self.assertContains(response, "Next five charges")
        self.assertContains(response, "Category mix")
        self.assertContains(response, "6-month spend curve")
        self.assertContains(response, "Netflix")
        self.assertContains(response, "$15.49")
        self.assertContains(response, "Streaming")
        self.assertContains(response, "Last synced")
        self.assertContains(response, "Portfolio overview")

    def test_dashboard_orders_active_subscriptions_before_cancelled_ones(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Zoom",
            normalized_vendor="zoom",
            amount="18.00",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_SOFTWARE,
            status=Subscription.STATUS_CANCELLED,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
            status=Subscription.STATUS_ACTIVE,
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active")
        self.assertContains(response, "Cancelled")
        self.assertLess(response.content.index(b"Netflix"), response.content.index(b"Zoom"))

    def test_candidates_page_renders_review_ui_for_pending_candidates(self):
        SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            source_transaction_ids=["txn_spotify_001", "txn_spotify_002"],
        )

        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recurring charge review queue")
        self.assertContains(response, "Pending subscription candidates")
        self.assertContains(response, "Spotify")
        self.assertContains(response, "Confirm subscription")
        self.assertContains(response, "Reject")
        self.assertContains(response, "Queue status")

    def test_candidates_page_shows_empty_state_when_no_candidates_exist(self):
        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending candidates yet.")

    def test_dashboard_only_shows_current_users_data(self):
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        Subscription.objects.create(
            user=other_user,
            merchant_name="Hidden Service",
            normalized_vendor="hidden service",
            amount="99.00",
            currency="USD",
            cadence="monthly",
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Hidden Service")

    def test_manual_add_page_renders(self):
        response = self.client.get(self.add_subscription_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add a subscription")
        self.assertContains(response, "Save subscription")
