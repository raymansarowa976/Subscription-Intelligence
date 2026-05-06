from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import (
    EmailScanRun,
    EmailSubscriptionLead,
    Subscription,
    SubscriptionCandidate,
    TransactionEvidence,
    TransactionImportRun,
)


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
        self.assertContains(response, "Scan email for subscriptions")
        self.assertContains(response, "Scan inbox now")
        self.assertContains(response, 'id="inbox-scan-panel"', html=False)
        self.assertContains(response, 'hx-post="/dashboard/email/scan/"', html=False)
        self.assertContains(response, 'hx-target="#inbox-scan-panel"', html=False)
        self.assertContains(response, 'hx-disabled-elt="find button"', html=False)
        self.assertContains(response, "Scanning...")
        self.assertContains(response, "No inbox scan has been run yet for this account.")
        self.assertNotContains(response, "Quick add subscription")
        self.assertNotContains(response, "Import transactions")
        self.assertNotContains(response, "Run transaction import")
        self.assertContains(response, "Active subscriptions tracked right now.")
        self.assertNotContains(response, "Likely subscriptions from email")
        self.assertNotContains(response, "Next five charges")
        self.assertNotContains(response, "Potential savings")

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
        import_run = TransactionImportRun.objects.create(
            user=self.user,
            provider="plaid",
            account_id="acct_dashboard",
            status=TransactionImportRun.STATUS_SUCCEEDED,
            requested_transaction_count=1,
            ingested_transactions=1,
        )
        TransactionEvidence.objects.create(
            user=self.user,
            import_run=import_run,
            provider="plaid",
            account_id="acct_dashboard",
            provider_transaction_id="txn_sync_001",
            merchant_name="Netflix",
            normalized_merchant_name="netflix",
            description="NETFLIX.COM",
            amount="15.49",
            currency="USD",
            posted_at=date.today(),
        )
        email_scan = EmailScanRun.objects.create(
            user=self.user,
            mailbox="INBOX",
            status=EmailScanRun.STATUS_SUCCEEDED,
            scanned_message_count=12,
            matched_message_count=2,
        )
        EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=email_scan,
            message_id="<msg-1@example.com>",
            sender="billing@netflix.com",
            sender_name="Netflix",
            subject="Your Netflix monthly receipt",
            merchant_name="Netflix",
            snippet="Your Netflix subscription will renew next month.",
            confidence_score=84,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hello, productuser, you have 1 renewal this week.")
        self.assertContains(response, "$25.49")
        self.assertContains(response, "$305.88")
        self.assertContains(response, "Category mix")
        self.assertContains(response, "6-month spend curve")
        self.assertContains(response, "Portfolio overview")
        self.assertContains(response, "Review subscriptions")
        self.assertContains(response, "Last inbox scan:")

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
        self.assertContains(response, "Active subscriptions tracked right now.")
        self.assertContains(response, "Inactive")
        self.assertEqual(response.context["active_subscription_count"], 1)
        self.assertEqual(response.context["inactive_subscription_count"], 1)

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
        self.assertContains(response, "Review subscriptions")
        self.assertContains(response, "Recurring subscription candidates")
        self.assertContains(response, "Spotify")
        self.assertContains(response, "Confirm subscription")
        self.assertContains(response, "Reject")
        self.assertContains(response, 'id="candidate-review-list"', html=False)
        self.assertContains(response, 'hx-post="', html=False)
        self.assertContains(response, 'hx-target="#candidate-review-list"', html=False)
        self.assertContains(response, 'hx-disabled-elt="find button"', html=False)
        self.assertContains(response, "Saving...")
        self.assertContains(response, "Dismissing...")
        self.assertContains(response, "Likely subscriptions from email")
        self.assertContains(response, "Next five charges")
        self.assertContains(response, "Potential savings")
        self.assertContains(response, "Source health")

    def test_htmx_confirm_candidate_refreshes_candidate_list_partial(self):
        candidate = SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            source_transaction_ids=["txn_spotify_001", "txn_spotify_002"],
        )
        TransactionEvidence.objects.create(
            user=self.user,
            provider="plaid",
            account_id="acct_review",
            provider_transaction_id="txn_spotify_001",
            merchant_name="Spotify",
            normalized_merchant_name="spotify",
            amount="10.99",
            currency="USD",
            posted_at=date.today(),
        )

        response = self.client.post(
            reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="candidate-review-list"', html=False)
        self.assertContains(response, 'hx-swap-oob="true"', html=False)
        self.assertContains(response, "Subscription saved")
        self.assertContains(response, "No pending candidates yet.")
        self.assertNotContains(response, "Subscription review workspace")
        self.assertEqual(Subscription.objects.filter(user=self.user, merchant_name="Spotify").count(), 1)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_CONFIRMED)

    def test_htmx_reject_candidate_refreshes_candidate_list_partial(self):
        candidate = SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            source_transaction_ids=["txn_spotify_001", "txn_spotify_002"],
        )

        response = self.client.post(
            reverse("transactions:reject_candidate", kwargs={"candidate_id": candidate.id}),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="candidate-review-list"', html=False)
        self.assertContains(response, "Candidate dismissed")
        self.assertContains(response, "No pending candidates yet.")
        self.assertNotContains(response, "Subscription review workspace")
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_REJECTED)

    def test_candidates_page_shows_empty_state_when_no_candidates_exist(self):
        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending candidates yet.")
        self.assertContains(response, "Run an inbox scan to surface likely subscription emails here.")

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
