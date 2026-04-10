from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import SubscriptionCandidate

User = get_user_model()


class TransactionIngestionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ingestionuser",
            email="ingestion@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

        self.sample_payload = {
            "provider": "plaid",
            "account_id": "acct_123",
            "transactions": [
                {
                    "provider_transaction_id": "txn_netflix_001",
                    "merchant_name": "Netflix",
                    "description": "NETFLIX.COM",
                    "amount": "15.49",
                    "currency": "USD",
                    "posted_at": "2026-04-01",
                },
                {
                    "provider_transaction_id": "txn_netflix_002",
                    "merchant_name": "Netflix",
                    "description": "NETFLIX.COM",
                    "amount": "15.49",
                    "currency": "USD",
                    "posted_at": "2026-03-01",
                },
            ],
        }

    def test_authenticated_verified_user_can_post_transaction_ingestion_payload(self):
        response = self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertEqual(response.json()["provider"], "plaid")
        self.assertEqual(response.json()["ingested_transactions"], 2)

    def test_ingestion_requires_authenticated_verified_session(self):
        self.client.logout()

        response = self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_ingestion_rejects_duplicate_provider_transaction_ids(self):
        self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        duplicate_response = self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        self.assertEqual(duplicate_response.status_code, 202)
        self.assertEqual(duplicate_response.json()["ingested_transactions"], 0)
        self.assertEqual(duplicate_response.json()["duplicate_transactions"], 2)

    def test_recurring_transactions_create_a_pending_subscription_candidate(self):
        self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        response = self.client.get(reverse("transactions:candidates"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending subscription candidates")
        self.assertContains(response, "Netflix")
        self.assertContains(response, "Monthly")
        self.assertContains(response, "$15.49")

    def test_one_off_transaction_does_not_create_subscription_candidate(self):
        payload = {
            "provider": "plaid",
            "account_id": "acct_123",
            "transactions": [
                {
                    "provider_transaction_id": "txn_bestbuy_001",
                    "merchant_name": "Best Buy",
                    "description": "BESTBUY #1234",
                    "amount": "799.99",
                    "currency": "USD",
                    "posted_at": "2026-04-01",
                }
            ],
        }

        self.client.post(
            reverse("transactions:ingest"),
            data=payload,
            content_type="application/json",
        )

        response = self.client.get(reverse("transactions:candidates"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Best Buy")

    def test_user_can_confirm_a_subscription_candidate(self):
        self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        response = self.client.post(
            reverse("transactions:confirm_candidate", kwargs={"candidate_id": 1}),
            data={"action": "confirm"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription saved")
        self.assertContains(response, "Netflix")
        self.assertContains(response, "Active subscriptions")

    def test_user_can_reject_a_subscription_candidate(self):
        self.client.post(
            reverse("transactions:ingest"),
            data=self.sample_payload,
            content_type="application/json",
        )

        response = self.client.post(
            reverse("transactions:reject_candidate", kwargs={"candidate_id": 1}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Candidate dismissed")
        self.assertEqual(
            SubscriptionCandidate.objects.get(pk=1).status,
            SubscriptionCandidate.STATUS_REJECTED,
        )

    def test_user_can_manually_add_a_subscription(self):
        response = self.client.post(
            reverse("transactions:add_subscription"),
            data={
                "merchant_name": "YouTube Premium",
                "amount": "13.99",
                "currency": "USD",
                "cadence": "monthly",
                "category": "streaming",
                "next_renewal": "2026-04-20",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription added")
        self.assertContains(response, "YouTube Premium")
