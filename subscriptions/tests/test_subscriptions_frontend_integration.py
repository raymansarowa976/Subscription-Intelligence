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
        self.subscription_results_url = "/dashboard/subscriptions/"
        self.candidates_url = reverse("transactions:candidates")
        self.add_subscription_url = reverse("transactions:add_subscription")
        self.contact_url = reverse("contact")
        self.gmail_integrations_url = "/dashboard/gmail/"
        self.analytics_url = "/dashboard/analytics/"
        self.data_sources_url = "/dashboard/data-sources/"

    def test_dashboard_renders_metrics_workspace_and_empty_states(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Total monthly spend")
        self.assertContains(response, "Upcoming renewals")
        self.assertContains(response, "Annual run-rate")
        self.assertContains(response, "Subscriptions")
        self.assertContains(response, "Log out")
        self.assertContains(response, "Contact support")
        self.assertContains(response, self.contact_url)
        self.assertContains(response, 'id="dashboard-inbox-lead-count-value"', html=False)
        self.assertContains(response, 'id="dashboard-review-queue-count-value"', html=False)
        self.assertContains(response, "Discovery pipeline")
        self.assertContains(response, "Found")
        self.assertContains(response, "Review")
        self.assertContains(response, "Tracked")
        self.assertContains(response, "Email matches move from found signals into review")
        self.assertNotContains(response, "Inbox leads")
        self.assertNotContains(response, "Review queue")
        self.assertNotContains(response, "Scan email for subscriptions")
        self.assertNotContains(response, "Scan inbox now")
        self.assertNotContains(response, 'id="inbox-scan-panel"', html=False)
        self.assertNotContains(response, 'hx-post="/dashboard/email/scan/"', html=False)
        self.assertNotContains(response, "Scanning...")
        self.assertContains(response, "Connect Gmail to unlock inbox scanning")
        self.assertContains(response, self.gmail_integrations_url)
        self.assertContains(response, "First workspace setup")
        self.assertContains(response, "Turn this empty dashboard into a renewal map.")
        self.assertContains(response, "Step 1")
        self.assertContains(response, "Step 2")
        self.assertContains(response, "Step 3")
        self.assertNotContains(response, "Quick add subscription")
        self.assertNotContains(response, "Import transactions")
        self.assertNotContains(response, "Run transaction import")
        self.assertContains(response, "Active subscriptions tracked right now.")
        content = response.content.decode()
        self.assertLess(content.index("Portfolio overview"), content.index("Personalized snapshot"))
        self.assertLess(content.index("Personalized snapshot"), content.index("Total monthly spend"))
        self.assertNotContains(response, "Spending by category")
        self.assertNotContains(response, "Monthly trend")
        self.assertNotContains(response, "6-month spend curve")
        self.assertNotContains(response, "categoryChart")
        self.assertNotContains(response, "trendChart")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/chart.js")
        self.assertNotContains(response, "Likely subscriptions from email")
        self.assertNotContains(response, "Next five charges")
        self.assertNotContains(response, "Potential savings")

    def test_dashboard_displays_confirmed_subscriptions_and_personalized_metrics_without_reports(self):
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
        self.assertNotContains(response, "Category mix")
        self.assertNotContains(response, "6-month spend curve")
        self.assertContains(response, self.analytics_url)
        self.assertContains(response, "Portfolio overview")
        self.assertContains(response, "Review Pending Items")
        self.assertNotContains(response, "Last inbox scan:")
        self.assertNotContains(response, "First workspace setup")

    def test_dashboard_emphasizes_review_cta_when_candidates_are_pending(self):
        SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            source_transaction_ids=["txn_spotify_001", "txn_spotify_002"],
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="dashboard-review-cta"', html=False)
        self.assertContains(response, "Review Pending Items")
        self.assertContains(response, "shadow-pine/20")
        self.assertNotContains(response, "Review subscriptions")
        self.assertEqual(response.content.decode().count('id="dashboard-review-cta"'), 1)

    def test_dashboard_has_exactly_one_primary_review_pending_items_action(self):
        EmailScanRun.objects.create(
            user=self.user,
            mailbox="connected@gmail.com",
            status=EmailScanRun.STATUS_SUCCEEDED,
            scanned_message_count=12,
            matched_message_count=2,
        )
        SubscriptionCandidate.objects.create(
            user=self.user,
            merchant_name="Spotify",
            normalized_vendor="spotify",
            amount="10.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
        )

        response = self.client.get(self.dashboard_url)
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(content.count("Review Pending Items"), 1)
        self.assertEqual(content.count('href="/transactions/candidates/"'), 1)
        self.assertNotContains(response, "Review matches")
        self.assertNotContains(response, "Review subscriptions")
        self.assertNotContains(response, "Scan inbox now")
        self.assertNotContains(response, "Run inbox scan")

    def test_dashboard_sidebar_links_to_standalone_ecosystem_pages(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.gmail_integrations_url)
        self.assertContains(response, self.analytics_url)
        self.assertContains(response, self.data_sources_url)
        self.assertNotContains(response, ">Soon<", html=False)

    def test_dashboard_scan_tools_are_gated_until_gmail_is_connected(self):
        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect Gmail to unlock inbox scanning")
        self.assertContains(response, self.gmail_integrations_url)
        self.assertNotContains(response, reverse("scan_inbox"))
        self.assertNotContains(response, "Scan inbox now")

    def test_scan_post_without_connected_gmail_redirects_to_guided_onboarding(self):
        response = self.client.post(reverse("scan_inbox"))

        self.assertRedirects(response, self.gmail_integrations_url)
        self.assertFalse(EmailScanRun.objects.filter(user=self.user).exists())

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

    def test_dashboard_renders_htmx_subscription_filters(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="subscription-filter-form"', html=False)
        self.assertContains(response, 'role="search"', html=False)
        self.assertContains(response, 'id="subscription-results"', html=False)
        self.assertContains(response, 'name="q"', html=False)
        self.assertContains(response, 'type="search"', html=False)
        self.assertContains(response, 'autocomplete="off"', html=False)
        self.assertContains(response, 'hx-get="/dashboard/subscriptions/"', html=False)
        self.assertContains(response, 'hx-trigger="keyup changed delay:300ms"', html=False)
        self.assertContains(response, 'hx-target="#subscription-results"', html=False)
        self.assertContains(response, 'hx-swap="outerHTML"', html=False)
        self.assertContains(response, 'hx-push-url="false"', html=False)
        self.assertContains(response, 'hx-include="#subscription-filter-form"', html=False)
        self.assertContains(response, 'name="category"', html=False)
        self.assertContains(response, 'aria-label="Filter subscriptions by category"', html=False)
        self.assertContains(response, "Streaming")
        self.assertContains(response, "Software")
        self.assertContains(response, "Netflix")

    def test_htmx_subscription_search_filters_results_on_keyup_contract(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Adobe Creative Cloud",
            normalized_vendor="adobe creative cloud",
            amount="59.99",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_SOFTWARE,
        )

        response = self.client.get(
            self.subscription_results_url,
            {"q": "net"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="subscription-results"', html=False)
        self.assertContains(response, 'data-active-query="net"', html=False)
        self.assertContains(response, 'data-active-category=""', html=False)
        self.assertContains(response, 'aria-live="polite"', html=False)
        self.assertContains(response, "Netflix")
        self.assertNotContains(response, "Adobe Creative Cloud")
        self.assertNotContains(response, "Portfolio overview")
        self.assertNotContains(response, "<html", html=False)

    def test_htmx_subscription_category_filter_updates_results_partial(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Notion",
            normalized_vendor="notion",
            amount="10.00",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_SOFTWARE,
        )

        response = self.client.get(
            self.subscription_results_url,
            {"category": Subscription.CATEGORY_SOFTWARE},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="subscription-results"', html=False)
        self.assertContains(response, 'data-active-query=""', html=False)
        self.assertContains(response, f'data-active-category="{Subscription.CATEGORY_SOFTWARE}"', html=False)
        self.assertContains(response, "1 subscription")
        self.assertContains(response, "Notion")
        self.assertContains(response, "Software")
        self.assertNotContains(response, "Netflix")
        self.assertNotContains(response, "Portfolio overview")

    def test_htmx_subscription_filters_show_clear_empty_state_when_no_results_match(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )

        response = self.client.get(
            self.subscription_results_url,
            {"q": "does-not-exist", "category": Subscription.CATEGORY_SOFTWARE},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="subscription-results"', html=False)
        self.assertContains(response, "No subscriptions match those filters")
        self.assertContains(response, "No subscriptions match \"does-not-exist\" in Software")
        self.assertContains(response, "Clear filters")
        self.assertNotContains(response, "Netflix")

    def test_htmx_subscription_filtering_preserves_user_data_isolation(self):
        other_user = User.objects.create_user(
            username="otherfilteruser",
            email="otherfilter@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )
        Subscription.objects.create(
            user=other_user,
            merchant_name="Netflix Team Account",
            normalized_vendor="netflix team account",
            amount="99.00",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )

        response = self.client.get(
            self.subscription_results_url,
            {"q": "netflix", "category": Subscription.CATEGORY_STREAMING},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-result-count="1"', html=False)
        self.assertContains(response, "Netflix")
        self.assertNotContains(response, "Netflix Team Account")

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
        self.assertContains(response, 'id="candidate-count-value"', html=False)
        self.assertContains(response, 'id="review-inbox-lead-count-value"', html=False)
        self.assertContains(response, 'id="upcoming-renewal-count-value"', html=False)
        self.assertContains(response, 'id="latest-inbox-scan-value"', html=False)
        self.assertContains(response, 'hx-post="', html=False)
        self.assertContains(response, 'hx-target="#candidate-review-list"', html=False)
        self.assertContains(response, 'hx-push-url="false"', html=False)
        self.assertContains(response, 'hx-disabled-elt="find button"', html=False)
        self.assertContains(response, 'data-htmx-polish', html=False)
        self.assertContains(response, 'htmx-idle-label', html=False)
        self.assertContains(response, "Saving...")
        self.assertContains(response, "Dismissing...")
        self.assertContains(response, "Likely subscriptions from email")
        self.assertContains(response, "Showing matches at 50% confidence or higher.")
        self.assertContains(response, "Next five charges")
        self.assertContains(response, "Potential savings")
        self.assertNotContains(response, "Source health")
        self.assertContains(response, self.data_sources_url)

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
        self.assertContains(response, 'id="candidate-count-value"', html=False)
        self.assertContains(response, 'id="upcoming-renewal-count-value"', html=False)
        self.assertContains(response, 'id="latest-inbox-scan-value"', html=False)
        self.assertContains(response, 'id="candidate-review-notice"', html=False)
        self.assertContains(response, 'role="status"', html=False)
        self.assertContains(response, 'aria-live="polite"', html=False)
        self.assertContains(response, 'data-htmx-focus-target', html=False)
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
        self.assertContains(response, 'hx-swap-oob="true"', html=False)
        self.assertContains(response, 'id="candidate-count-value"', html=False)
        self.assertContains(response, 'id="upcoming-renewal-count-value"', html=False)
        self.assertContains(response, 'id="candidate-review-notice"', html=False)
        self.assertContains(response, 'data-htmx-focus-target', html=False)
        self.assertContains(response, "Candidate dismissed")
        self.assertContains(response, "No pending candidates yet.")
        self.assertNotContains(response, "Subscription review workspace")
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_REJECTED)

    def test_candidates_page_shows_empty_state_when_no_candidates_exist(self):
        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No pending candidates yet")
        self.assertContains(response, "No high-confidence inbox matches")
        self.assertContains(response, "Renewal calendar is waiting")

    def test_candidates_page_hides_low_confidence_and_newsletter_email_leads(self):
        scan = EmailScanRun.objects.create(
            user=self.user,
            mailbox="INBOX",
            status=EmailScanRun.STATUS_SUCCEEDED,
            scanned_message_count=29,
            matched_message_count=3,
        )
        visible_lead = EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=scan,
            message_id="<billing@example.com>",
            sender="billing@streambox.example",
            sender_name="StreamBox Billing",
            subject="Your StreamBox monthly receipt",
            merchant_name="StreamBox",
            snippet="Total paid: $12.99. Next billing date: May 4, 2026.",
            confidence_score=86,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )
        SubscriptionCandidate.objects.create(
            user=self.user,
            source_type=SubscriptionCandidate.SOURCE_EMAIL_RECEIPT,
            source_email_lead=visible_lead,
            merchant_name="StreamBox",
            normalized_vendor="streambox",
            amount="12.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            confidence_score=86,
            likely_renewal_date=date(2026, 5, 4),
        )
        EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=scan,
            message_id="<newsletter@example.com>",
            sender="quincy@example.com",
            sender_name="Quincy Larson",
            subject="Weekly coding newsletter",
            merchant_name="Quincy Larson",
            snippet="This week's community update and unsubscribe link.",
            confidence_score=72,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )
        EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=scan,
            message_id="<weak@example.com>",
            sender="hello@beem.example",
            sender_name="Beem Credit Union",
            subject="Account update",
            merchant_name="Beem Credit Union",
            snippet="A general account notice.",
            confidence_score=30,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )

        response = self.client.get(self.candidates_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "StreamBox")
        self.assertContains(response, "$12.99")
        self.assertContains(response, "May 4, 2026")
        self.assertContains(response, "Dismiss 2 low-signal")
        self.assertContains(response, "29 processed - 3 matched")
        self.assertNotContains(response, "Quincy Larson")
        self.assertNotContains(response, "Beem Credit Union")

    def test_bulk_dismiss_inbox_leads_clears_newsletter_and_low_confidence_noise(self):
        scan = EmailScanRun.objects.create(user=self.user, mailbox="INBOX")
        strong_lead = EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=scan,
            message_id="<strong@example.com>",
            sender="billing@streambox.example",
            sender_name="StreamBox Billing",
            subject="Your StreamBox receipt",
            merchant_name="StreamBox",
            snippet="Receipt for your monthly plan.",
            confidence_score=80,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )
        newsletter = EmailSubscriptionLead.objects.create(
            user=self.user,
            scan_run=scan,
            message_id="<noise@example.com>",
            sender="news@example.com",
            sender_name="Mermaid",
            subject="Mermaid weekly newsletter",
            merchant_name="Mermaid",
            snippet="Product updates and unsubscribe.",
            confidence_score=70,
            received_at=timezone.make_aware(datetime.combine(date.today(), datetime.min.time())),
        )

        response = self.client.post(
            reverse("transactions:bulk_dismiss_inbox_leads"),
            {"action": "noise"},
            follow=True,
        )

        self.assertRedirects(response, self.candidates_url)
        strong_lead.refresh_from_db()
        newsletter.refresh_from_db()
        self.assertEqual(strong_lead.status, EmailSubscriptionLead.STATUS_PENDING)
        self.assertEqual(newsletter.status, EmailSubscriptionLead.STATUS_DISMISSED)

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
