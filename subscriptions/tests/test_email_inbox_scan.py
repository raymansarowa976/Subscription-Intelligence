from datetime import datetime
from email.message import EmailMessage
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from subscriptions.models import EmailScanRun, EmailSubscriptionLead
from subscriptions.services import InboxScanError, scan_email_inbox_for_subscriptions
from subscriptions.tasks import scan_email_inbox_task


User = get_user_model()


def _build_message(subject, sender, message_id, body, sent_at):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "user@example.com"
    message["Date"] = sent_at.strftime("%a, %d %b %Y %H:%M:%S +0000")
    message["Message-ID"] = message_id
    message.set_content(body)
    return message.as_bytes()


class FakeIMAP4:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.messages = {
            b"1": _build_message(
                subject="Your Netflix monthly receipt",
                sender="Netflix Billing <billing@netflix.com>",
                message_id="<netflix-1@example.com>",
                body="Your subscription payment was received for your monthly Netflix plan.",
                sent_at=datetime(2026, 4, 1, 12, 0, 0),
            ),
            b"2": _build_message(
                subject="Welcome to Best Buy Rewards",
                sender="Best Buy <news@bestbuy.com>",
                message_id="<bestbuy-1@example.com>",
                body="Thanks for shopping with Best Buy this week.",
                sent_at=datetime(2026, 4, 2, 12, 0, 0),
            ),
        }

    def login(self, username, password):
        if username != "user@gmail.com" or password != "app-password":
            raise AssertionError("Unexpected inbox credentials in test")
        return "OK", [b"logged-in"]

    def select(self, mailbox):
        return "OK", [b"2"]

    def search(self, charset, *criteria):
        return "OK", [b"1 2"]

    def fetch(self, identifier, query):
        return "OK", [(b"BODY[]", self.messages[identifier])]

    def logout(self):
        return "BYE", [b"logout"]


@override_settings(
    IMAP_HOST="imap.gmail.com",
    IMAP_PORT=993,
    IMAP_USERNAME="user@gmail.com",
    IMAP_PASSWORD="app-password",
    IMAP_MAILBOX="INBOX",
    EMAIL_SCAN_LOOKBACK_DAYS=90,
    EMAIL_SCAN_MAX_MESSAGES=25,
)
class EmailInboxScanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mailuser",
            email="mailuser@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

    @patch("subscriptions.services.imaplib.IMAP4_SSL", new=FakeIMAP4)
    def test_scan_email_inbox_persists_likely_subscription_leads(self):
        result = scan_email_inbox_for_subscriptions(self.user)

        self.assertEqual(result["mailbox"], "INBOX")
        self.assertEqual(result["scanned_message_count"], 2)
        self.assertEqual(result["matched_message_count"], 1)
        self.assertEqual(result["new_lead_count"], 1)

        lead = EmailSubscriptionLead.objects.get(user=self.user)
        self.assertEqual(lead.merchant_name, "Netflix")
        self.assertIn("monthly receipt", lead.subject.lower())
        self.assertGreaterEqual(lead.confidence_score, 30)

        scan_run = EmailScanRun.objects.get(user=self.user)
        self.assertEqual(scan_run.status, EmailScanRun.STATUS_SUCCEEDED)
        self.assertEqual(scan_run.matched_message_count, 1)

    @patch("subscriptions.services.imaplib.IMAP4_SSL", new=FakeIMAP4)
    def test_scan_inbox_view_runs_scan_and_shows_success_feedback(self):
        response = self.client.post(reverse("scan_inbox"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inbox scan complete.")
        self.assertContains(response, "Review subscriptions")
        self.assertContains(response, "Your Netflix monthly receipt")
        self.assertContains(response, "Likely subscriptions from email")

    @patch("subscriptions.services.imaplib.IMAP4_SSL", new=FakeIMAP4)
    def test_huey_task_runs_inbox_scan_outside_request_response_cycle(self):
        result = scan_email_inbox_task.call_local(self.user.id)

        self.assertEqual(result["scanned_message_count"], 2)
        self.assertEqual(result["matched_message_count"], 1)
        self.assertEqual(EmailSubscriptionLead.objects.filter(user=self.user).count(), 1)

    def test_scan_inbox_view_can_enqueue_background_scan(self):
        with patch("subscriptions.views.scan_email_inbox_task", return_value=object()) as scan_task:
            response = self.client.post(reverse("scan_inbox"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        scan_task.assert_called_once_with(self.user.id)
        self.assertContains(response, "Inbox scan queued.")
        self.assertContains(response, 'id="inbox-scan-notice"', html=False)

    @patch("subscriptions.services.imaplib.IMAP4_SSL", new=FakeIMAP4)
    def test_htmx_scan_inbox_view_returns_dashboard_feedback_panel(self):
        response = self.client.post(reverse("scan_inbox"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="dashboard-inbox-lead-count-value"', html=False)
        self.assertContains(response, 'id="dashboard-review-queue-count-value"', html=False)
        self.assertContains(response, 'hx-swap-oob="true"', html=False)
        self.assertContains(response, 'id="inbox-scan-panel"', html=False)
        self.assertContains(response, 'id="inbox-scan-notice"', html=False)
        self.assertContains(response, 'role="status"', html=False)
        self.assertContains(response, 'aria-live="polite"', html=False)
        self.assertContains(response, 'data-htmx-focus-target', html=False)
        self.assertContains(response, "Inbox scan complete. Checked 2 messages and found 1 likely subscription emails.")
        self.assertContains(response, "Last inbox scan:")
        self.assertContains(response, "Review matches")
        self.assertNotContains(response, "Subscription review workspace")

    @override_settings(IMAP_USERNAME="", IMAP_PASSWORD="")
    def test_htmx_scan_inbox_view_returns_error_feedback_panel(self):
        response = self.client.post(reverse("scan_inbox"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="dashboard-inbox-lead-count-value"', html=False)
        self.assertContains(response, 'hx-swap-oob="true"', html=False)
        self.assertContains(response, 'id="inbox-scan-panel"', html=False)
        self.assertContains(response, 'id="inbox-scan-notice"', html=False)
        self.assertContains(response, 'role="status"', html=False)
        self.assertContains(response, "Inbox credentials are not configured.")
        self.assertContains(response, "Scan inbox now")
        self.assertNotContains(response, "Subscription review workspace")

    @override_settings(IMAP_USERNAME="", IMAP_PASSWORD="")
    def test_scan_email_inbox_requires_configured_credentials(self):
        with self.assertRaises(InboxScanError):
            scan_email_inbox_for_subscriptions(self.user)
