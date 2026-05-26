from datetime import date
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from subscriptions.models import Subscription, TransactionEvidence
from subscriptions.services import build_dashboard_context


User = get_user_model()


class MultiCurrencySupportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="currencyuser",
            email="currency@gmail.com",
            password="Complex123!",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["login_token_verified"] = True
        session.save()

    def _assert_user_base_currency_support(self, currency="USD"):
        if not hasattr(self.user, "base_currency"):
            self.fail("Users must store a base_currency used for subscription reporting.")
        self.user.base_currency = currency
        self.user.save(update_fields=["base_currency"])

    def _exchange_rate_model(self):
        try:
            return apps.get_model("subscriptions", "ExchangeRate")
        except LookupError:
            self.fail("subscriptions.ExchangeRate must define dated exchange rates.")

    def _create_rate(self, from_currency, to_currency, rate, effective_date):
        return self._exchange_rate_model().objects.create(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=Decimal(rate),
            effective_date=effective_date,
        )

    def test_dashboard_total_spend_converts_subscriptions_to_users_base_currency(self):
        self._create_rate("EUR", "USD", "1.10", date(2026, 1, 1))
        self._create_rate("CAD", "USD", "0.75", date(2026, 1, 1))
        self._assert_user_base_currency_support("USD")
        Subscription.objects.create(
            user=self.user,
            merchant_name="US Stream",
            normalized_vendor="us stream",
            amount="10.00",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Euro Notes",
            normalized_vendor="euro notes",
            amount="10.00",
            currency="EUR",
            cadence="monthly",
            category=Subscription.CATEGORY_SOFTWARE,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Canada Cloud",
            normalized_vendor="canada cloud",
            amount="120.00",
            currency="CAD",
            cadence="yearly",
            category=Subscription.CATEGORY_SOFTWARE,
        )

        context = build_dashboard_context(self.user)

        self.assertEqual(context["base_currency"], "USD")
        self.assertEqual(context["total_monthly_spend"], Decimal("28.50"))
        self.assertEqual(context["annual_run_rate"], Decimal("342.00"))
        self.assertEqual(context["currency_symbol"], "$")

    def test_historical_exchange_rates_are_used_for_monthly_transaction_trends(self):
        self._create_rate("EUR", "USD", "1.10", date(2026, 1, 1))
        self._create_rate("EUR", "USD", "1.20", date(2026, 2, 1))
        self._assert_user_base_currency_support("USD")
        TransactionEvidence.objects.create(
            user=self.user,
            provider="plaid",
            account_id="acct_currency",
            provider_transaction_id="txn_eur_jan",
            merchant_name="Euro Service",
            normalized_merchant_name="euro service",
            amount="10.00",
            currency="EUR",
            posted_at=date(2026, 1, 15),
        )
        TransactionEvidence.objects.create(
            user=self.user,
            provider="plaid",
            account_id="acct_currency",
            provider_transaction_id="txn_eur_feb",
            merchant_name="Euro Service",
            normalized_merchant_name="euro service",
            amount="10.00",
            currency="EUR",
            posted_at=date(2026, 2, 15),
        )

        context = build_dashboard_context(self.user)
        trend_by_month = dict(zip(context["trend_labels"], context["trend_values"], strict=True))

        self.assertEqual(Decimal(str(trend_by_month["Jan"])), Decimal("11.0"))
        self.assertEqual(Decimal(str(trend_by_month["Feb"])), Decimal("12.0"))

    def test_dashboard_and_subscription_results_display_currency_symbols_from_model_data(self):
        Subscription.objects.create(
            user=self.user,
            merchant_name="US Stream",
            normalized_vendor="us stream",
            amount="10.00",
            currency="USD",
            cadence="monthly",
            category=Subscription.CATEGORY_STREAMING,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="Euro Notes",
            normalized_vendor="euro notes",
            amount="10.00",
            currency="EUR",
            cadence="monthly",
            category=Subscription.CATEGORY_SOFTWARE,
        )
        Subscription.objects.create(
            user=self.user,
            merchant_name="London News",
            normalized_vendor="london news",
            amount="8.00",
            currency="GBP",
            cadence="monthly",
            category=Subscription.CATEGORY_OTHER,
        )

        response = self.client.get(reverse("subscription_results"))

        self.assertContains(response, "$10.00 USD")
        self.assertContains(response, "€10.00 EUR")
        self.assertContains(response, "£8.00 GBP")
        self.assertNotContains(response, "$10.00 EUR")
        self.assertNotContains(response, "$8.00 GBP")

    def test_currency_models_define_rate_direction_and_historical_uniqueness(self):
        ExchangeRate = self._exchange_rate_model()
        field_names = {field.name for field in ExchangeRate._meta.fields}
        constraint_names = {constraint.name for constraint in ExchangeRate._meta.constraints}

        self.assertIn("from_currency", field_names)
        self.assertIn("to_currency", field_names)
        self.assertIn("rate", field_names)
        self.assertIn("effective_date", field_names)
        self.assertIn("uniq_exchange_rate_currency_pair_per_day", constraint_names)

    def test_users_store_a_base_currency_for_reporting(self):
        self._assert_user_base_currency_support("CAD")
        self.user.refresh_from_db()

        self.assertEqual(self.user.base_currency, "CAD")
