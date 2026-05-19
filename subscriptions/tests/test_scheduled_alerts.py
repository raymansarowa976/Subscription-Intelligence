from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from subscriptions.models import Subscription
from subscriptions.tasks import send_renewal_alerts_task, subscriptions_renewing_in_48_hours


User = get_user_model()


class ScheduledRenewalAlertsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alertuser",
            email="alertuser@example.com",
            password="Complex123!",
            is_active=True,
        )
        self.today = date(2026, 5, 10)
        self.renewal_date = self.today + timedelta(days=2)
        self.due_subscription = Subscription.objects.create(
            user=self.user,
            merchant_name="Netflix",
            normalized_vendor="netflix",
            amount="15.49",
            currency="USD",
            cadence="monthly",
            next_renewal=self.renewal_date,
        )

    def test_mock_task_identifies_subscriptions_renewing_in_48_hours(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="Adobe",
            normalized_vendor="adobe",
            amount="120.00",
            currency="USD",
            cadence="yearly",
            next_renewal=self.today + timedelta(days=3),
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Cancelled",
            normalized_vendor="cancelled",
            amount="9.99",
            currency="USD",
            cadence="monthly",
            next_renewal=self.renewal_date,
            status=Subscription.STATUS_CANCELLED,
        )

        with patch("subscriptions.tasks.timezone.localdate", return_value=self.today):
            result = send_renewal_alerts_task.call_local()

        self.assertEqual(result["sent_count"], 1)
        self.assertEqual(result["target_date"], self.renewal_date.isoformat())
        self.assertEqual(result["subscription_ids"], [self.due_subscription.id])
        due_subscriptions = list(subscriptions_renewing_in_48_hours(self.today))
        self.assertEqual(due_subscriptions, [self.due_subscription])

    def test_mail_outbox_contains_subscription_name_amount_and_renewal_date(self):
        with patch("subscriptions.tasks.timezone.localdate", return_value=self.today):
            send_renewal_alerts_task.call_local()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.user.email])
        self.assertIn("Netflix", message.subject)
        self.assertIn("Netflix", message.body)
        self.assertIn("$15.49", message.body)
        self.assertIn("May 12, 2026", message.body)
