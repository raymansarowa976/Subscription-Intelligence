from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import EmailConnection, EmailScanRun
from subscriptions.tasks import scan_email_inbox_task
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class AccountSettingsPreferencesContractTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="settingscontract",
            email="settingscontract@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()

    def _scan_preference_model(self):
        return apps.get_model("subscriptions", "EmailScanPreference")

    def _gmail_connection(self, **overrides):
        defaults = {
            "user": self.user,
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

    def test_account_settings_uses_simple_content_layout_without_in_page_sidebar(self):
        response = self.client.get(reverse("accounts:account_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-settings-layout="account-settings"', html=False)
        self.assertContains(response, 'data-settings-pane="profile"', html=False)
        self.assertContains(response, 'data-settings-pane="security"', html=False)
        self.assertContains(response, 'data-settings-pane="data-export"', html=False)
        self.assertNotContains(response, 'aria-label="Account settings sections"', html=False)
        self.assertNotContains(response, 'data-settings-sidebar="account"', html=False)

    def test_account_settings_links_to_isolated_danger_zone_at_bottom_without_rendering_forms(self):
        response = self.client.get(reverse("accounts:account_settings"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("accounts:danger_zone"))
        self.assertContains(response, "Danger Zone")
        self.assertContains(response, "Open Danger Zone")
        self.assertGreater(content.index("Danger Zone"), content.index("Manage account data"))
        self.assertNotContains(response, f'action="{reverse("accounts:delete_imported_evidence")}"', html=False)
        self.assertNotContains(response, f'action="{reverse("accounts:close_account")}"', html=False)

    def test_danger_zone_owns_destructive_actions_and_masks_confirmation_passwords(self):
        response = self.client.get(reverse("accounts:danger_zone"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Danger Zone")
        self.assertContains(response, "Delete imported evidence")
        self.assertContains(response, "Close account")
        self.assertContains(response, f'action="{reverse("accounts:delete_imported_evidence")}"', html=False)
        self.assertContains(response, f'action="{reverse("accounts:close_account")}"', html=False)
        self.assertContains(response, 'name="password"', html=False)
        self.assertContains(response, 'data-password-toggle="danger-delete-password"', html=False)
        self.assertContains(response, 'data-password-toggle="danger-close-password"', html=False)
        self.assertContains(response, 'aria-label="Show password"', html=False)

    def test_account_settings_microcopy_uses_clear_action_headings(self):
        response = self.client.get(reverse("accounts:account_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Update your username")
        self.assertContains(response, "Update your password")
        self.assertContains(response, "Reporting currency")
        self.assertContains(response, "Manage account data")
        self.assertNotContains(response, "Change username")
        self.assertNotContains(response, "Change password")

    def test_account_settings_renders_base_currency_preference_controls(self):
        self.user.base_currency = "CAD"
        self.user.save(update_fields=["base_currency"])

        response = self.client.get(reverse("accounts:account_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporting currency")
        self.assertContains(response, "Dashboard totals and analytics convert into this currency.")
        self.assertContains(response, f'action="{reverse("accounts:update_base_currency")}"', html=False)
        self.assertContains(response, 'name="base_currency"', html=False)
        self.assertContains(response, 'aria-label="Base reporting currency"', html=False)
        self.assertContains(response, '<option value="USD"', html=False)
        self.assertContains(response, '<option value="CAD" selected', html=False)
        self.assertContains(response, '<option value="EUR"', html=False)
        self.assertContains(response, '<option value="GBP"', html=False)

    def test_revoked_gmail_permission_blocks_background_scans_and_persists_warning_state(self):
        connection = self._gmail_connection(
            status=EmailConnection.STATUS_DISCONNECTED,
            access_token="",
            refresh_token="",
        )

        with patch("subscriptions.services.fetch_gmail_messages") as fetch_messages:
            result = scan_email_inbox_task.call_local(self.user.id, connection.id)

        fetch_messages.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "Reconnect Gmail to scan this mailbox.")
        failed_scan = EmailScanRun.objects.get(user=self.user, email_connection=connection)
        self.assertEqual(failed_scan.status, EmailScanRun.STATUS_FAILED)
        self.assertEqual(failed_scan.error_details["warning_state"], "gmail_permission_revoked")

    def test_token_verified_login_queues_automatic_scan_for_active_gmail_connection(self):
        connection = self._gmail_connection()
        ScanPreference = self._scan_preference_model()
        ScanPreference.objects.create(user=self.user, automatic_scans=True)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = False
        session.save()

        with (
            patch("users.auth.views.verify_email_token", return_value=True),
            patch("users.auth.views.clear_email_token"),
            patch("users.auth.views.scan_email_inbox_task") as scan_task,
        ):
            response = self.client.post(reverse("accounts:verify_token"), {"token": "123456"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard"))
        scan_task.assert_called_once_with(self.user.id, connection.id)

    def test_scan_preferences_render_and_persist_intervals_and_email_selection_rules(self):
        ScanPreference = self._scan_preference_model()
        model_field_names = {field.name for field in ScanPreference._meta.get_fields()}
        self.assertIn("scan_intervals", model_field_names)
        self.assertIn("email_selection_rules", model_field_names)

        response = self.client.get(reverse("gmail_integrations"))
        self.assertContains(response, 'name="scan_intervals"', html=False)
        self.assertContains(response, 'value="daily"', html=False)
        self.assertContains(response, 'value="weekly"', html=False)
        self.assertContains(response, 'name="email_selection_rules"', html=False)

        self.client.post(
            reverse("accounts:update_privacy_controls"),
            {
                "scan_scope": "billing_mail",
                "retention_period_days": "90",
                "automatic_scans": "on",
                "scan_intervals": ["daily", "weekly"],
                "email_selection_rules": "from:(receipts@example.com) subject:(invoice OR receipt)",
            },
        )

        preferences = ScanPreference.objects.get(user=self.user)
        self.assertEqual(preferences.scan_intervals, ["daily", "weekly"])
        self.assertEqual(
            preferences.email_selection_rules,
            "from:(receipts@example.com) subject:(invoice OR receipt)",
        )
