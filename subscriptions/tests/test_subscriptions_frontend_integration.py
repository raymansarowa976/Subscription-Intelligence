from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import Subscription, SubscriptionCandidate


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

    def test_dashboard_renders_product_shell_and_empty_states(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription command center")
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Candidates")
        self.assertContains(response, "No subscriptions confirmed yet.")
        self.assertContains(response, "Open review queue")

    def test_dashboard_displays_confirmed_subscriptions(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Netflix")
        self.assertContains(response, "$15.49")
        self.assertContains(response, "Monthly recurring charge")

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
        self.assertContains(response, "Queue status")

    def test_candidates_page_shows_empty_state_when_no_candidates_exist(self):
        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending candidates yet.")
