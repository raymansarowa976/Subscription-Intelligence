from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from subscriptions.models import EmailScanRun, EmailSubscriptionLead, Subscription, SubscriptionCandidate
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class SubscriptionReviewPageFullFunctionalityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reviewuser",
            email="reviewuser@example.com",
            password="Complex123!",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="otherreviewuser",
            email="otherreviewuser@example.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()
        self.candidates_url = reverse("transactions:candidates")

    def _verified_client(self, user):
        client = Client()
        client.force_login(user)
        session = client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()
        return client

    def _scan(self, user=None, **overrides):
        defaults = {
            "user": user or self.user,
            "mailbox": "INBOX",
            "status": EmailScanRun.STATUS_SUCCEEDED,
            "scanned_message_count": 12,
            "matched_message_count": 3,
        }
        defaults.update(overrides)
        return EmailScanRun.objects.create(**defaults)

    def _lead(self, user=None, scan_run=None, **overrides):
        owner = user or self.user
        defaults = {
            "user": owner,
            "scan_run": scan_run or self._scan(owner),
            "message_id": f"<lead-{owner.pk}-{EmailSubscriptionLead.objects.count()}@example.com>",
            "sender": "billing@streambox.example",
            "sender_name": "StreamBox Billing",
            "subject": "Your StreamBox monthly receipt",
            "merchant_name": "StreamBox",
            "snippet": "Total paid: $12.99. Next billing date: June 4, 2026.",
            "cleaned_body": "Receipt for your monthly subscription.",
            "confidence_score": 85,
            "received_at": timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        }
        defaults.update(overrides)
        return EmailSubscriptionLead.objects.create(**defaults)

    def _candidate(self, user=None, lead=None, **overrides):
        owner = user or self.user
        defaults = {
            "user": owner,
            "source_type": SubscriptionCandidate.SOURCE_EMAIL_RECEIPT,
            "source_email_lead": lead,
            "merchant_name": "StreamBox",
            "normalized_vendor": "streambox",
            "amount": "12.99",
            "currency": "USD",
            "cadence": SubscriptionCandidate.CADENCE_MONTHLY,
            "confidence_score": 85,
            "source_transaction_ids": [],
            "billing_date": date(2026, 5, 4),
            "likely_renewal_date": date(2026, 6, 4),
        }
        defaults.update(overrides)
        return SubscriptionCandidate.objects.create(**defaults)

    @override_settings(REVIEWABLE_INBOX_CONFIDENCE_THRESHOLD=80)
    def test_confidence_threshold_is_configurable_and_boundary_values_are_respected(self):
        scan = self._scan()
        below = self._lead(scan_run=scan, merchant_name="Below Threshold", confidence_score=79)
        at_threshold = self._lead(scan_run=scan, merchant_name="At Threshold", confidence_score=80)
        above = self._lead(scan_run=scan, merchant_name="Above Threshold", confidence_score=81)
        self._candidate(lead=below, merchant_name="Below Threshold", normalized_vendor="below threshold", confidence_score=79)
        self._candidate(lead=at_threshold, merchant_name="At Threshold", normalized_vendor="at threshold", confidence_score=80)
        self._candidate(lead=above, merchant_name="Above Threshold", normalized_vendor="above threshold", confidence_score=81)

        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Below Threshold")
        self.assertContains(response, "At Threshold")
        self.assertContains(response, "Above Threshold")
        self.assertContains(response, "Showing matches at 80% confidence or higher.")

    def test_confirming_email_candidate_marks_source_lead_confirmed_and_is_idempotent(self):
        lead = self._lead()
        candidate = self._candidate(lead=lead)
        url = reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id})

        first_response = self.client.post(url, follow=True)
        second_response = self.client.post(url, follow=True)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        lead.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(lead.status, EmailSubscriptionLead.STATUS_CONFIRMED)
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_CONFIRMED)
        self.assertEqual(Subscription.objects.filter(user=self.user, merchant_name="StreamBox").count(), 1)

    def test_rejecting_email_candidate_dismisses_source_lead_and_is_idempotent(self):
        lead = self._lead()
        candidate = self._candidate(lead=lead)
        url = reverse("transactions:reject_candidate", kwargs={"candidate_id": candidate.id})

        first_response = self.client.post(url, follow=True)
        second_response = self.client.post(url, follow=True)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        lead.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(lead.status, EmailSubscriptionLead.STATUS_DISMISSED)
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_REJECTED)

    def test_review_actions_require_verified_login_token_sessions(self):
        lead = self._lead()
        candidate = self._candidate(lead=lead)
        unverified = Client()
        unverified.force_login(self.user)
        routes = [
            reverse("transactions:candidates"),
            reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id}),
            reverse("transactions:reject_candidate", kwargs={"candidate_id": candidate.id}),
            reverse("transactions:bulk_dismiss_inbox_leads"),
        ]

        for route in routes:
            with self.subTest(route=route):
                response = unverified.post(route) if route != self.candidates_url else unverified.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("accounts:verify_token"), response["Location"])

    def test_bulk_dismiss_supports_form_fallback_htmx_updates_and_user_isolation(self):
        own_noise = self._lead(
            sender_name="Weekly Newsletter",
            subject="Weekly newsletter",
            snippet="Marketing update and unsubscribe.",
            confidence_score=72,
        )
        own_billing = self._lead(confidence_score=90)
        other_noise = self._lead(
            user=self.other_user,
            sender_name="Other Newsletter",
            subject="Other weekly newsletter",
            snippet="Marketing update and unsubscribe.",
            confidence_score=72,
        )

        normal_response = self.client.post(reverse("transactions:bulk_dismiss_inbox_leads"), {"action": "noise"})
        htmx_response = self.client.post(
            reverse("transactions:bulk_dismiss_inbox_leads"),
            {"action": "noise"},
            HTTP_HX_REQUEST="true",
        )

        self.assertRedirects(normal_response, self.candidates_url)
        self.assertEqual(htmx_response.status_code, 200)
        self.assertContains(htmx_response, 'id="candidate-review-list"', html=False)
        self.assertContains(htmx_response, 'id="review-inbox-lead-count-value"', html=False)
        own_noise.refresh_from_db()
        own_billing.refresh_from_db()
        other_noise.refresh_from_db()
        self.assertEqual(own_noise.status, EmailSubscriptionLead.STATUS_DISMISSED)
        self.assertEqual(own_billing.status, EmailSubscriptionLead.STATUS_PENDING)
        self.assertEqual(other_noise.status, EmailSubscriptionLead.STATUS_PENDING)

    def test_one_user_cannot_mutate_another_users_candidates_or_leads(self):
        other_client = self._verified_client(self.other_user)
        lead = self._lead()
        candidate = self._candidate(lead=lead)
        forbidden_routes = [
            reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id}),
            reverse("transactions:reject_candidate", kwargs={"candidate_id": candidate.id}),
        ]
        per_lead_route_names = [
            "dismiss_inbox_lead",
            "restore_inbox_lead",
            "mark_inbox_lead_newsletter",
        ]
        for route_name in per_lead_route_names:
            try:
                forbidden_routes.append(reverse(f"transactions:{route_name}", kwargs={"lead_id": lead.id}))
            except NoReverseMatch:
                forbidden_routes.append(route_name)

        for route in forbidden_routes:
            with self.subTest(route=route):
                if route in per_lead_route_names:
                    self.fail(f"Missing protected route transactions:{route}")
                response = other_client.post(route)
                self.assertIn(response.status_code, [403, 404])

        lead.refresh_from_db()
        candidate.refresh_from_db()
        self.assertEqual(lead.status, EmailSubscriptionLead.STATUS_PENDING)
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_PENDING)

    def test_per_lead_and_selected_bulk_actions_exist_and_update_counts_out_of_band(self):
        lead = self._lead()
        route_expectations = [
            ("dismiss_inbox_lead", {"lead_id": lead.id}, {"action": "dismiss"}),
            ("mark_inbox_lead_newsletter", {"lead_id": lead.id}, {"action": "newsletter"}),
            ("restore_inbox_lead", {"lead_id": lead.id}, {"action": "restore"}),
            ("bulk_update_inbox_leads", {}, {"lead_ids": [lead.id], "action": "dismiss"}),
        ]

        for route_name, kwargs, payload in route_expectations:
            with self.subTest(route_name=route_name):
                url = reverse(f"transactions:{route_name}", kwargs=kwargs)
                response = self.client.post(url, payload, HTTP_HX_REQUEST="true")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="review-inbox-lead-count-value"', html=False)
                self.assertContains(response, 'hx-swap-oob="true"', html=False)
                self.assertContains(response, "Filtered out")

    def test_confirm_candidate_accepts_valid_edits_and_prevents_duplicate_subscription_creation(self):
        lead = self._lead()
        candidate = self._candidate(lead=lead)
        url = reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id})
        payload = {
            "merchant_name": "Edited StreamBox",
            "amount": "19.99",
            "currency": "USD",
            "cadence": SubscriptionCandidate.CADENCE_YEARLY,
            "category": Subscription.CATEGORY_SOFTWARE,
            "next_renewal": "2026-12-31",
        }

        first_response = self.client.post(url, payload, follow=True)
        second_response = self.client.post(url, payload, follow=True)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        subscription = Subscription.objects.get(user=self.user, merchant_name="Edited StreamBox")
        self.assertEqual(str(subscription.amount), "19.99")
        self.assertEqual(subscription.cadence, SubscriptionCandidate.CADENCE_YEARLY)
        self.assertEqual(subscription.category, Subscription.CATEGORY_SOFTWARE)
        self.assertEqual(subscription.next_renewal, date(2026, 12, 31))
        self.assertEqual(Subscription.objects.filter(user=self.user, merchant_name="Edited StreamBox").count(), 1)

    def test_invalid_candidate_edits_return_errors_without_creating_subscription(self):
        lead = self._lead()
        candidate = self._candidate(lead=lead)

        response = self.client.post(
            reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id}),
            {
                "merchant_name": "",
                "amount": "-1.00",
                "currency": "USD",
                "cadence": "weekly",
                "next_renewal": "not-a-date",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a merchant name")
        self.assertContains(response, "Enter a valid amount")
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_PENDING)

    def test_dashboard_counts_match_filtered_review_queue_and_update_after_actions(self):
        hidden = self._lead(merchant_name="Hidden Low Confidence", confidence_score=20)
        visible = self._lead(merchant_name="Visible Billing", confidence_score=92)
        self._candidate(lead=hidden, merchant_name="Hidden Low Confidence", normalized_vendor="hidden", confidence_score=20)
        candidate = self._candidate(lead=visible, merchant_name="Visible Billing", normalized_vendor="visible", confidence_score=92)

        dashboard_before = self.client.get(reverse("dashboard"))
        review_before = self.client.get(self.candidates_url)
        self.client.post(reverse("transactions:confirm_candidate", kwargs={"candidate_id": candidate.id}), follow=True)
        dashboard_after = self.client.get(reverse("dashboard"))

        self.assertContains(dashboard_before, 'id="dashboard-inbox-lead-count-value"', html=False)
        self.assertContains(dashboard_before, ">1<", html=False)
        self.assertContains(review_before, 'id="review-inbox-lead-count-value"', html=False)
        self.assertContains(review_before, ">1<", html=False)
        self.assertContains(dashboard_after, 'id="dashboard-inbox-lead-count-value"', html=False)
        self.assertContains(dashboard_after, ">0<", html=False)

    def test_source_health_displays_succeeded_failed_queued_and_in_progress_scan_states(self):
        now = timezone.now()
        self._scan(status=EmailScanRun.STATUS_SUCCEEDED, scanned_message_count=50, matched_message_count=8, completed_at=now)
        self._scan(status=EmailScanRun.STATUS_FAILED, scanned_message_count=10, matched_message_count=0)
        self._scan(status="queued", scanned_message_count=0, matched_message_count=0)
        self._scan(status="in_progress", scanned_message_count=5, matched_message_count=1)

        response = self.client.get(reverse("data_sources"))

        self.assertContains(response, "Succeeded")
        self.assertContains(response, "Failed")
        self.assertContains(response, "Queued")
        self.assertContains(response, "In progress")
        self.assertContains(response, "50 processed - 8 matched")
        self.assertContains(response, "Duration")
        self.assertContains(response, "Parser candidates")

    def test_review_filters_are_bookmarkable_isolated_and_have_resettable_empty_states(self):
        own_lead = self._lead(merchant_name="Own StreamBox", confidence_score=90)
        other_lead = self._lead(user=self.other_user, merchant_name="Other StreamBox", confidence_score=95)
        self._candidate(lead=own_lead, merchant_name="Own StreamBox", normalized_vendor="own streambox", confidence_score=90)
        self._candidate(
            user=self.other_user,
            lead=other_lead,
            merchant_name="Other StreamBox",
            normalized_vendor="other streambox",
            confidence_score=95,
        )

        response = self.client.get(
            self.candidates_url,
            {
                "q": "missing",
                "source": SubscriptionCandidate.SOURCE_EMAIL_RECEIPT,
                "confidence": "high",
                "status": SubscriptionCandidate.STATUS_PENDING,
                "cadence": SubscriptionCandidate.CADENCE_MONTHLY,
                "sort": "confidence",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="source"', html=False)
        self.assertContains(response, 'name="confidence"', html=False)
        self.assertContains(response, 'name="status"', html=False)
        self.assertContains(response, 'name="cadence"', html=False)
        self.assertContains(response, 'name="sort"', html=False)
        self.assertContains(response, "No review items match those filters")
        self.assertContains(response, "Reset filters")
        self.assertNotContains(response, "Other StreamBox")

    def test_candidate_cards_have_accessible_disclosures_and_text_overflow_guards(self):
        lead = self._lead(
            subject="Your StreamBox monthly receipt with an unusually long subject that should wrap cleanly",
            cleaned_body="A very long receipt body " * 80,
        )
        self._candidate(lead=lead)

        response = self.client.get(self.candidates_url)

        self.assertContains(response, "<details", html=False)
        self.assertContains(response, "<summary", html=False)
        self.assertContains(response, "candidate-review-card", html=False)
        self.assertContains(response, "[&::-webkit-details-marker]:hidden", html=False)
        self.assertContains(response, "Review")
        self.assertContains(response, "Hide")
        self.assertContains(response, "focus-visible", html=False)
        self.assertContains(response, "break-words", html=False)
        self.assertContains(response, "overflow-hidden", html=False)
        self.assertContains(response, "Parser confidence")
        self.assertContains(response, "Extracted fields")

    def test_leads_store_classification_filter_explanation_and_audit_metadata(self):
        lead = self._lead(
            confidence_score=20,
            subject="Marketing newsletter",
            snippet="Product update and unsubscribe link.",
        )

        self.assertTrue(hasattr(lead, "classification"))
        self.assertTrue(hasattr(lead, "classification_reason"))
        self.assertTrue(hasattr(lead, "last_action"))
        self.assertTrue(hasattr(lead, "last_action_at"))
        self.assertIn(lead.classification, ["billing_signal", "newsletter", "marketing", "low_confidence", "unknown"])

        response = self.client.get(self.candidates_url, {"view": "filtered"})

        self.assertContains(response, "Filtered out")
        self.assertContains(response, "Marketing newsletter")
        self.assertContains(response, "Why this was filtered")
        self.assertContains(response, "Restore")
