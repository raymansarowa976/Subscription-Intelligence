from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import ExchangeRate, Subscription, TransactionEvidence
from subscriptions.services import build_dashboard_context
from users.auth.views import LOGIN_TOKEN_VERIFIED_SESSION_KEY


User = get_user_model()


class AdvancedAnalyticsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="analyticsuser",
            email="analytics@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username="otheranalytics",
            email="otheranalytics@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[LOGIN_TOKEN_VERIFIED_SESSION_KEY] = True
        session.save()
        self.user.base_currency = "USD"
        self.user.save(update_fields=["base_currency"])

    def _subscription(self, **overrides):
        defaults = {
            "user": self.user,
            "merchant_name": "StreamBox",
            "normalized_vendor": "streambox",
            "amount": "20.00",
            "currency": "USD",
            "cadence": "monthly",
            "category": Subscription.CATEGORY_STREAMING,
            "status": Subscription.STATUS_ACTIVE,
        }
        defaults.update(overrides)
        return Subscription.objects.create(**defaults)

    def _transaction(self, **overrides):
        defaults = {
            "user": self.user,
            "provider": "manual",
            "account_id": "checking",
            "provider_transaction_id": f"txn-{TransactionEvidence.objects.count()}",
            "merchant_name": "StreamBox",
            "normalized_merchant_name": "streambox",
            "amount": "20.00",
            "currency": "USD",
            "posted_at": date.today().replace(day=5),
        }
        defaults.update(overrides)
        return TransactionEvidence.objects.create(**defaults)

    def test_analytics_aggregation_edge_cases_normalize_yearly_currency_and_cancelled_subscriptions(self):
        ExchangeRate.objects.create(
            from_currency="EUR",
            to_currency="USD",
            rate=Decimal("1.20"),
            effective_date=date(2026, 1, 1),
        )
        self._subscription(merchant_name="StreamBox", normalized_vendor="streambox", amount="20.00")
        self._subscription(
            merchant_name="Adobe",
            normalized_vendor="adobe",
            amount="120.00",
            cadence="yearly",
            category=Subscription.CATEGORY_SOFTWARE,
        )
        self._subscription(
            merchant_name="Euro News",
            normalized_vendor="euro news",
            amount="10.00",
            currency="EUR",
            category=Subscription.CATEGORY_STREAMING,
        )
        self._subscription(
            merchant_name="Cancelled Giant",
            normalized_vendor="cancelled giant",
            amount="999.00",
            category=Subscription.CATEGORY_SOFTWARE,
            status=Subscription.STATUS_CANCELLED,
        )

        context = build_dashboard_context(self.user)

        self.assertEqual(context["total_monthly_spend"], Decimal("42.00"))
        self.assertEqual(dict(zip(context["category_labels"], context["category_values"], strict=True))["Streaming"], 32.0)
        self.assertEqual(dict(zip(context["category_labels"], context["category_values"], strict=True))["Software"], 10.0)
        self.assertEqual(context["top_vendor_insights"][0]["merchant_name"], "StreamBox")
        self.assertNotIn("Cancelled Giant", [row["merchant_name"] for row in context["top_vendor_insights"]])

    def test_renewal_window_insights_group_upcoming_active_renewals(self):
        today = date.today()
        self._subscription(merchant_name="Due Soon", normalized_vendor="due soon", amount="10.00", next_renewal=today + timedelta(days=3))
        self._subscription(merchant_name="Due This Month", normalized_vendor="due this month", amount="20.00", next_renewal=today + timedelta(days=20))
        self._subscription(merchant_name="Later", normalized_vendor="later", amount="30.00", next_renewal=today + timedelta(days=60))
        self._subscription(
            merchant_name="Cancelled Soon",
            normalized_vendor="cancelled soon",
            amount="999.00",
            next_renewal=today + timedelta(days=2),
            status=Subscription.STATUS_CANCELLED,
        )

        context = build_dashboard_context(self.user)
        windows = {row["label"]: row for row in context["renewal_window_insights"]}

        self.assertEqual(windows["Next 7 days"]["count"], 1)
        self.assertEqual(windows["Next 7 days"]["amount"], Decimal("10.00"))
        self.assertEqual(windows["Next 30 days"]["count"], 2)
        self.assertEqual(windows["Next 30 days"]["amount"], Decimal("30.00"))
        self.assertEqual(windows["Beyond 30 days"]["count"], 1)
        self.assertEqual(windows["Beyond 30 days"]["amount"], Decimal("30.00"))

    def test_analytics_page_renders_deeper_insights_and_monthly_report_export_link(self):
        self._subscription(merchant_name="StreamBox", normalized_vendor="streambox", amount="20.00")
        self._subscription(
            merchant_name="Adobe",
            normalized_vendor="adobe",
            amount="120.00",
            cadence="yearly",
            category=Subscription.CATEGORY_SOFTWARE,
        )

        response = self.client.get(reverse("analytics"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vendor concentration")
        self.assertContains(response, "Category detail")
        self.assertContains(response, "Renewal windows")
        self.assertContains(response, "Monthly report")
        self.assertContains(response, reverse("analytics_monthly_report"))
        self.assertContains(response, "StreamBox")
        self.assertContains(response, "Adobe")

    def test_monthly_report_export_aggregates_current_user_transactions_only(self):
        report_month = date.today().replace(day=1)
        self._transaction(
            merchant_name="StreamBox",
            normalized_merchant_name="streambox",
            amount="20.00",
            posted_at=report_month.replace(day=5),
        )
        self._transaction(
            merchant_name="Adobe",
            normalized_merchant_name="adobe",
            amount="10.00",
            posted_at=report_month.replace(day=6),
        )
        self._transaction(
            user=self.other_user,
            merchant_name="Hidden Vendor",
            normalized_merchant_name="hidden vendor",
            amount="999.00",
            posted_at=report_month.replace(day=7),
            provider_transaction_id="txn-hidden",
        )

        response = self.client.get(reverse("analytics_monthly_report"), {"month": report_month.strftime("%Y-%m")})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        self.assertEqual(payload["month"], report_month.strftime("%Y-%m"))
        self.assertEqual(payload["base_currency"], "USD")
        self.assertEqual(payload["total_spend"], "30.00")
        self.assertEqual(payload["vendor_totals"][0]["merchant_name"], "StreamBox")
        self.assertEqual(payload["vendor_totals"][0]["amount"], "20.00")
        self.assertNotIn("Hidden Vendor", str(payload))
