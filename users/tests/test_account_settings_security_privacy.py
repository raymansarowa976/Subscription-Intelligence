from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import (
    EmailConnection,
    EmailScanRun,
    EmailSubscriptionLead,
    Subscription,
    SubscriptionCandidate,
    TransactionEvidence,
    TransactionImportRun,
)
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class AccountSettingsSecurityPrivacyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="settingsprivacy",
            email="settingsprivacy@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="otherprivacy",
            email="otherprivacy@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()
        self.account_settings_url = reverse("accounts:account_settings")

    def _login_verified_client(self, user):
        client = Client()
        client.force_login(user)
        session = client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()
        return client

    def _email_connection(self, user=None, **overrides):
        defaults = {
            "user": user or self.user,
            "provider": EmailConnection.PROVIDER_GMAIL,
            "email_address": "connected@gmail.com",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_expires_at": timezone.now() + timedelta(hours=1),
            "status": EmailConnection.STATUS_ACTIVE,
        }
        defaults.update(overrides)
        return EmailConnection.objects.create(**defaults)

    def _subscription_data(self, user=None):
        owner = user or self.user
        subscription = Subscription.objects.create(
            user=owner,
            merchant_name="StreamBox",
            normalized_vendor="streambox",
            amount="12.99",
            currency="USD",
            cadence="monthly",
            next_renewal=date(2026, 6, 1),
        )
        import_run = TransactionImportRun.objects.create(
            user=owner,
            provider="manual",
            account_id="checking",
            requested_transaction_count=1,
            ingested_transactions=1,
        )
        evidence = TransactionEvidence.objects.create(
            user=owner,
            import_run=import_run,
            provider="manual",
            account_id="checking",
            provider_transaction_id=f"txn-{owner.pk}",
            merchant_name="StreamBox",
            normalized_merchant_name="streambox",
            amount="12.99",
            currency="USD",
            posted_at=date(2026, 5, 1),
        )
        scan_run = EmailScanRun.objects.create(
            user=owner,
            provider="gmail",
            mailbox=owner.email,
            scanned_message_count=1,
            matched_message_count=1,
        )
        lead = EmailSubscriptionLead.objects.create(
            user=owner,
            scan_run=scan_run,
            message_id=f"message-{owner.pk}",
            sender="billing@streambox.example",
            subject="Your StreamBox receipt",
            merchant_name="StreamBox",
            received_at=timezone.now(),
            confidence_score=95,
        )
        candidate = SubscriptionCandidate.objects.create(
            user=owner,
            source_type=SubscriptionCandidate.SOURCE_EMAIL_RECEIPT,
            source_email_lead=lead,
            merchant_name="StreamBox",
            normalized_vendor="streambox",
            amount="12.99",
            currency="USD",
            cadence=SubscriptionCandidate.CADENCE_MONTHLY,
            source_transaction_ids=[evidence.provider_transaction_id],
            confidence_score=95,
        )
        return {
            "subscription": subscription,
            "evidence": evidence,
            "lead": lead,
            "candidate": candidate,
        }

    def test_account_settings_renders_security_privacy_controls_and_real_gmail_status(self):
        connection = self._email_connection(
            email_address="connected@gmail.com",
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
        )

        response = self.client.get(self.account_settings_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account overview")
        self.assertContains(response, "Active")
        self.assertContains(response, self.user.date_joined.strftime("%b"))
        self.assertContains(response, "Connected services")
        self.assertContains(response, "Recent activity")
        self.assertContains(response, "Change username")
        self.assertContains(response, "Change password")
        self.assertContains(response, "Danger zone")
        self.assertContains(response, "Log out other sessions")
        self.assertContains(response, "Export account data")
        self.assertContains(response, "Delete imported evidence")
        self.assertContains(response, "Close account")
        self.assertContains(response, "Privacy controls")
        self.assertContains(response, "Scan scope")
        self.assertContains(response, "Retention period")
        self.assertContains(response, "Automatic scans")
        self.assertContains(response, "connected@gmail.com")
        self.assertContains(response, "Token healthy")
        self.assertContains(response, "Last sync")
        self.assertContains(response, "https://www.googleapis.com/auth/gmail.readonly")
        self.assertContains(response, reverse("accounts:resync_gmail", kwargs={"connection_id": connection.id}))
        self.assertContains(response, reverse("accounts:revoke_gmail", kwargs={"connection_id": connection.id}))
        self.assertNotContains(response, "Kelowna, BC - 2 mins ago")

    def test_inline_username_form_preserves_validation_errors_in_account_settings_context(self):
        response = self.client.post(
            reverse("accounts:change_username"),
            {
                "new_username": "freshname",
                "confirm_username": "differentname",
                "current_password": "Complex123!",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account settings")
        self.assertContains(response, "Change username")
        self.assertContains(response, "Usernames do not match.")
        self.assertContains(response, 'name="confirm_username"', html=False)
        self.assertContains(response, "Danger zone")

    def test_inline_password_form_preserves_validation_errors_in_account_settings_context(self):
        response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "Wrong123!",
                "new_password": "Better456!",
                "confirm_password": "Better456!",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account settings")
        self.assertContains(response, "Change password")
        self.assertContains(response, "Enter your current password.")
        self.assertContains(response, 'id="password-strength-bar"', html=False)
        self.assertContains(response, "Danger zone")

    def test_user_can_log_out_other_active_sessions_while_preserving_current_session(self):
        other_client = self._login_verified_client(self.user)
        current_session_key = self.client.session.session_key
        other_session_key = other_client.session.session_key

        response = self.client.post(reverse("accounts:logout_other_sessions"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Other sessions have been logged out.")
        self.assertTrue(Session.objects.filter(session_key=current_session_key).exists())
        self.assertFalse(Session.objects.filter(session_key=other_session_key).exists())
        self.assertEqual(self.client.get(self.account_settings_url).status_code, 200)

    def test_account_deletion_and_data_deletion_require_password_and_typed_confirmation(self):
        self._subscription_data()

        delete_data_url = reverse("accounts:delete_imported_evidence")
        close_account_url = reverse("accounts:close_account")

        missing_confirmation = self.client.post(
            delete_data_url,
            {"password": "Complex123!", "confirmation": ""},
            follow=True,
        )
        wrong_password = self.client.post(
            close_account_url,
            {"password": "Wrong123!", "confirmation": "CLOSE ACCOUNT"},
            follow=True,
        )

        self.assertEqual(missing_confirmation.status_code, 200)
        self.assertContains(missing_confirmation, "Type DELETE DATA to confirm.")
        self.assertTrue(TransactionEvidence.objects.filter(user=self.user).exists())
        self.assertTrue(EmailSubscriptionLead.objects.filter(user=self.user).exists())
        self.assertEqual(wrong_password.status_code, 200)
        self.assertContains(wrong_password, "Enter your current password to continue.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_one_user_cannot_view_delete_or_export_another_users_account_subscription_data(self):
        other_records = self._subscription_data(user=self.other_user)
        other_connection = self._email_connection(user=self.other_user, email_address="other@gmail.com")

        forbidden_requests = [
            self.client.get(reverse("accounts:export_account_data_for_user", kwargs={"user_id": self.other_user.id})),
            self.client.post(
                reverse("accounts:delete_subscription", kwargs={"subscription_id": other_records["subscription"].id}),
                {"password": "Complex123!", "confirmation": "DELETE SUBSCRIPTION"},
            ),
            self.client.post(
                reverse("accounts:delete_imported_evidence_for_user", kwargs={"user_id": self.other_user.id}),
                {"password": "Complex123!", "confirmation": "DELETE DATA"},
            ),
            self.client.post(
                reverse("accounts:revoke_gmail", kwargs={"connection_id": other_connection.id}),
            ),
        ]

        for response in forbidden_requests:
            with self.subTest(status_code=response.status_code):
                self.assertIn(response.status_code, [403, 404])

        self.assertTrue(Subscription.objects.filter(pk=other_records["subscription"].id).exists())
        self.assertTrue(TransactionEvidence.objects.filter(pk=other_records["evidence"].id).exists())
        self.assertTrue(EmailSubscriptionLead.objects.filter(pk=other_records["lead"].id).exists())
        other_connection.refresh_from_db()
        self.assertEqual(other_connection.status, EmailConnection.STATUS_ACTIVE)

    def test_export_account_data_includes_only_the_current_users_account_and_subscription_data(self):
        own_records = self._subscription_data()
        other_records = self._subscription_data(user=self.other_user)

        response = self.client.get(reverse("accounts:export_account_data"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertContains(response, self.user.email)
        self.assertContains(response, own_records["subscription"].merchant_name)
        self.assertContains(response, own_records["lead"].subject)
        self.assertNotContains(response, self.other_user.email)
        self.assertNotContains(response, other_records["evidence"].provider_transaction_id)

    def test_gmail_resync_revoke_and_privacy_controls_post_card_level_feedback(self):
        connection = self._email_connection()

        privacy_response = self.client.post(
            reverse("accounts:update_privacy_controls"),
            {
                "scan_scope": "receipts_only",
                "retention_period_days": "90",
                "automatic_scans": "on",
            },
            follow=True,
        )
        resync_response = self.client.post(
            reverse("accounts:resync_gmail", kwargs={"connection_id": connection.id}),
            follow=True,
        )
        revoke_response = self.client.post(
            reverse("accounts:revoke_gmail", kwargs={"connection_id": connection.id}),
            follow=True,
        )

        self.assertContains(privacy_response, "Privacy controls saved.")
        self.assertContains(privacy_response, "Scan scope")
        self.assertContains(resync_response, "Gmail re-sync started.")
        self.assertContains(resync_response, "Connected services")
        self.assertContains(revoke_response, "Gmail access revoked.")
        self.assertContains(revoke_response, "Connected services")

    def test_destructive_disclosures_are_keyboard_and_screen_reader_addressable(self):
        response = self.client.get(self.account_settings_url)

        self.assertContains(response, 'aria-expanded="false"', html=False)
        self.assertContains(response, 'aria-controls="delete-imported-evidence-panel"', html=False)
        self.assertContains(response, 'id="delete-imported-evidence-panel"', html=False)
        self.assertContains(response, 'aria-controls="close-account-panel"', html=False)
        self.assertContains(response, 'id="close-account-panel"', html=False)
        self.assertContains(response, 'role="alert"', html=False)
        self.assertContains(response, 'aria-live="polite"', html=False)
