from datetime import datetime, timedelta
from email.message import EmailMessage
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY

from subscriptions.models import EmailConnection, EmailScanRun, EmailSubscriptionLead, SubscriptionCandidate
from subscriptions.services import InboxScanError, scan_email_inbox_for_subscriptions
from subscriptions.tasks import scan_email_inbox_task


User = get_user_model()


def _gmail_message(
    *,
    message_id="<gmail-receipt-1@example.com>",
    subject="Your StreamBox monthly receipt",
    sender="StreamBox Billing <billing@streambox.example>",
    body="Receipt from StreamBox\nTotal: $12.99\nBilling date: April 4, 2026\nNext billing date: May 4, 2026\nMonthly plan",
):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "connected@gmail.com"
    message["Date"] = "Sat, 04 Apr 2026 12:00:00 +0000"
    message["Message-ID"] = message_id
    message.set_content(body)
    return {
        "id": message_id.strip("<>"),
        "thread_id": "thread-1",
        "raw": message.as_bytes(),
    }


class EmailOAuthIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="oauthuser",
            email="oauthuser@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="othermailuser",
            email="othermailuser@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()

    def _email_connection_model(self):
        return apps.get_model("subscriptions", "EmailConnection")

    def _scan_preference_model(self):
        return apps.get_model("subscriptions", "EmailScanPreference")

    def _connection(self, user=None, **overrides):
        EmailConnection = self._email_connection_model()
        defaults = {
            "user": user or self.user,
            "provider": "gmail",
            "email_address": "connected@gmail.com",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_expires_at": timezone.now() + timedelta(hours=1),
            "status": EmailConnection.STATUS_ACTIVE,
        }
        defaults.update(overrides)
        return EmailConnection.objects.create(**defaults)

    def test_account_settings_starts_gmail_connection_flow(self):
        response = self.client.get(reverse("accounts:account_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Connect Gmail")
        self.assertNotContains(response, reverse("accounts:connect_gmail"))
        self.assertNotContains(response, "Gmail API")
        self.assertNotContains(response, "Email scan preferences")

    def test_gmail_integrations_page_owns_connection_state_and_sync_controls(self):
        connection = self._connection()
        EmailScanRun.objects.create(
            user=self.user,
            email_connection=connection,
            provider="gmail",
            mailbox="connected@gmail.com",
            status=EmailScanRun.STATUS_SUCCEEDED,
            scanned_message_count=12,
            matched_message_count=3,
        )

        response = self.client.get("/dashboard/gmail/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gmail integrations")
        self.assertContains(response, "connected@gmail.com")
        self.assertContains(response, "Token healthy")
        self.assertContains(response, "Connect Gmail")
        self.assertContains(response, reverse("accounts:connect_gmail"))
        self.assertContains(response, reverse("accounts:resync_gmail", kwargs={"connection_id": connection.id}))
        self.assertContains(response, reverse("accounts:revoke_gmail", kwargs={"connection_id": connection.id}))
        self.assertContains(response, reverse("accounts:disconnect_email_connection", kwargs={"connection_id": connection.id}))
        self.assertContains(response, "Automatic scans")
        self.assertContains(response, "Scan scope")

    @override_settings(
        GMAIL_OAUTH_CLIENT_ID="client-id",
        GMAIL_OAUTH_CLIENT_SECRET="client-secret",
        GMAIL_OAUTH_REDIRECT_URI="http://testserver/accounts/email/gmail/callback/",
    )
    def test_gmail_connect_redirects_with_state_and_readonly_scope(self):
        response = self.client.get(reverse("accounts:connect_gmail"))

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response["Location"])
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.netloc, "accounts.google.com")
        self.assertEqual(query["client_id"], ["client-id"])
        self.assertEqual(query["redirect_uri"], ["http://testserver/accounts/email/gmail/callback/"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertIn("https://www.googleapis.com/auth/gmail.readonly", query["scope"][0])
        self.assertEqual(query["state"], [self.client.session["gmail_oauth_state"]])

    @override_settings(
        GMAIL_OAUTH_CLIENT_ID="client-id",
        GMAIL_OAUTH_CLIENT_SECRET="client-secret",
        GMAIL_OAUTH_REDIRECT_URI="http://testserver/accounts/email/gmail/callback/",
    )
    def test_gmail_callback_links_mailbox_to_current_authenticated_user(self):
        session = self.client.session
        session["gmail_oauth_state"] = "state-token"
        session.save()

        token_payload = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
        }
        profile_payload = {"emailAddress": "connected@gmail.com"}

        with (
            patch("users.auth.views.exchange_gmail_oauth_code", return_value=token_payload),
            patch("users.auth.views.fetch_gmail_profile", return_value=profile_payload),
        ):
            response = self.client.get(
                reverse("accounts:gmail_oauth_callback"),
                {"state": "state-token", "code": "oauth-code"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, "/dashboard/gmail/")
        EmailConnection = self._email_connection_model()
        connection = EmailConnection.objects.get(email_address="connected@gmail.com")
        self.assertEqual(connection.user, self.user)
        self.assertEqual(connection.provider, "gmail")
        self.assertEqual(connection.scopes, ["https://www.googleapis.com/auth/gmail.readonly"])
        self.assertEqual(connection.status, EmailConnection.STATUS_ACTIVE)
        self.assertGreater(connection.token_expires_at, timezone.now())
        self.assertNotEqual(connection.access_token, "new-access-token")
        self.assertNotEqual(connection.refresh_token, "new-refresh-token")

    @override_settings(
        GMAIL_OAUTH_CLIENT_ID="client-id",
        GMAIL_OAUTH_CLIENT_SECRET="client-secret",
        GMAIL_OAUTH_REDIRECT_URI="http://testserver/accounts/email/gmail/callback/",
    )
    def test_gmail_callback_queues_scan_when_automatic_scans_are_enabled(self):
        ScanPreference = self._scan_preference_model()
        ScanPreference.objects.create(
            user=self.user,
            scan_scope="receipts_only",
            retention_period_days=90,
            automatic_scans=True,
        )
        session = self.client.session
        session["gmail_oauth_state"] = "state-token"
        session.save()

        token_payload = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
        }
        profile_payload = {"emailAddress": "connected@gmail.com"}

        with (
            patch("users.auth.views.exchange_gmail_oauth_code", return_value=token_payload),
            patch("users.auth.views.fetch_gmail_profile", return_value=profile_payload),
            patch("users.auth.views.scan_email_inbox_task") as scan_task,
        ):
            response = self.client.get(
                reverse("accounts:gmail_oauth_callback"),
                {"state": "state-token", "code": "oauth-code"},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, "/dashboard/gmail/")
        connection = EmailConnection.objects.get(user=self.user, email_address="connected@gmail.com")
        scan_task.assert_called_once_with(self.user.id, connection.id)

    def test_gmail_callback_rejects_invalid_oauth_state(self):
        session = self.client.session
        session["gmail_oauth_state"] = "expected-state"
        session.save()

        response = self.client.get(
            reverse("accounts:gmail_oauth_callback"),
            {"state": "tampered-state", "code": "oauth-code"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email connection could not be verified.")
        EmailConnection = self._email_connection_model()
        self.assertFalse(EmailConnection.objects.filter(user=self.user).exists())

    def test_one_user_cannot_scan_another_users_connected_mailbox(self):
        other_connection = self._connection(user=self.other_user, email_address="other@gmail.com")

        with self.assertRaises(InboxScanError):
            scan_email_inbox_for_subscriptions(self.user, email_connection_id=other_connection.id)

        self.assertFalse(EmailScanRun.objects.filter(user=self.user, provider="gmail").exists())
        self.assertFalse(EmailSubscriptionLead.objects.filter(user=self.user).exists())

    @override_settings(IMAP_USERNAME="global@example.com", IMAP_PASSWORD="global-password")
    def test_inbox_scan_uses_current_users_oauth_connection_instead_of_global_imap_credentials(self):
        connection = self._connection()

        with (
            patch("subscriptions.services.imaplib.IMAP4_SSL", side_effect=AssertionError("IMAP fallback was used")),
            patch("subscriptions.services.fetch_gmail_messages", return_value=[_gmail_message()]) as fetch_messages,
        ):
            result = scan_email_inbox_for_subscriptions(self.user, email_connection_id=connection.id)

        fetch_messages.assert_called_once_with(connection, query=fetch_messages.call_args.kwargs["query"])
        self.assertEqual(result["provider"], "gmail")
        self.assertEqual(result["mailbox"], "connected@gmail.com")
        self.assertEqual(result["scanned_message_count"], 1)
        self.assertEqual(result["matched_message_count"], 1)

        lead = EmailSubscriptionLead.objects.get(user=self.user)
        self.assertEqual(lead.subject, "Your StreamBox monthly receipt")
        self.assertEqual(lead.sender, "billing@streambox.example")
        self.assertEqual(lead.scan_run.provider, "gmail")
        self.assertEqual(lead.scan_run.mailbox, "connected@gmail.com")

    @override_settings(IMAP_USERNAME="global@example.com", IMAP_PASSWORD="global-password")
    def test_scan_inbox_view_defaults_to_current_users_active_oauth_connection(self):
        connection = self._connection()

        with (
            patch("subscriptions.services.imaplib.IMAP4_SSL", side_effect=AssertionError("IMAP fallback was used")),
            patch("subscriptions.services.fetch_gmail_messages", return_value=[_gmail_message()]),
        ):
            response = self.client.post(reverse("scan_inbox"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inbox scan complete. Checked 1 messages and found 1 likely subscription emails.")
        scan_run = EmailScanRun.objects.get(user=self.user)
        self.assertEqual(scan_run.provider, "gmail")
        self.assertEqual(scan_run.email_connection, connection)

    def test_disconnected_email_connections_do_not_run_scans_and_show_feedback(self):
        EmailConnection = self._email_connection_model()
        connection = self._connection(status=EmailConnection.STATUS_DISCONNECTED)

        with patch("subscriptions.services.fetch_gmail_messages") as fetch_messages:
            response = self.client.post(
                reverse("scan_inbox"),
                {"email_connection_id": connection.id},
                HTTP_HX_REQUEST="true",
            )

        fetch_messages.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reconnect Gmail to scan this mailbox.")
        self.assertFalse(EmailScanRun.objects.filter(user=self.user, provider="gmail").exists())

    def test_background_scan_task_blocks_revoked_gmail_connection(self):
        EmailConnection = self._email_connection_model()
        connection = self._connection(status=EmailConnection.STATUS_DISCONNECTED)

        with patch("subscriptions.services.fetch_gmail_messages") as fetch_messages:
            result = scan_email_inbox_task.call_local(self.user.id, connection.id)

        fetch_messages.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "Reconnect Gmail to scan this mailbox.")
        self.assertFalse(EmailScanRun.objects.filter(user=self.user, provider="gmail").exists())

    def test_expired_email_connection_refreshes_before_scanning(self):
        expired_at = timezone.make_aware(datetime(2026, 4, 1, 12, 0, 0))
        connection = self._connection(token_expires_at=expired_at)

        with (
            patch("subscriptions.services.refresh_gmail_access_token") as refresh_token,
            patch("subscriptions.services.fetch_gmail_messages", return_value=[]),
        ):
            scan_email_inbox_for_subscriptions(self.user, email_connection_id=connection.id)

        refresh_token.assert_called_once_with(connection)

    def test_gmail_scan_refreshes_and_retries_when_stored_access_token_is_rejected(self):
        connection = self._connection()

        with (
            patch("subscriptions.services.refresh_gmail_access_token") as refresh_token,
            patch(
                "subscriptions.services.fetch_gmail_messages",
                side_effect=[InboxScanError("Reconnect Gmail to scan this mailbox."), []],
            ) as fetch_messages,
        ):
            result = scan_email_inbox_for_subscriptions(self.user, email_connection_id=connection.id)

        refresh_token.assert_called_once_with(connection)
        self.assertEqual(fetch_messages.call_count, 2)
        self.assertEqual(result["provider"], "gmail")
        self.assertEqual(result["scanned_message_count"], 0)

    def test_existing_receipt_parser_creates_review_candidates_from_oauth_fetched_messages(self):
        connection = self._connection()

        with patch("subscriptions.services.fetch_gmail_messages", return_value=[_gmail_message()]):
            result = scan_email_inbox_task.call_local(self.user.id, connection.id)

        self.assertEqual(result["provider"], "gmail")
        lead = EmailSubscriptionLead.objects.get(user=self.user)
        candidate = SubscriptionCandidate.objects.get(user=self.user, source_email_lead=lead)
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_PENDING)
        self.assertEqual(candidate.source_type, SubscriptionCandidate.SOURCE_EMAIL_RECEIPT)
        self.assertEqual(candidate.merchant_name, "StreamBox")
        self.assertEqual(str(candidate.amount), "12.99")

    def test_user_can_disconnect_connected_mailbox(self):
        EmailConnection = self._email_connection_model()
        connection = self._connection()

        response = self.client.post(
            reverse("accounts:disconnect_email_connection", kwargs={"connection_id": connection.id}),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, "/dashboard/gmail/")
        connection.refresh_from_db()
        self.assertEqual(connection.status, EmailConnection.STATUS_DISCONNECTED)
        self.assertContains(response, "Gmail disconnected.")
