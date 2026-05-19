from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from subscriptions.models import EmailSubscriptionLead, Subscription, SubscriptionCandidate
from subscriptions.receipt_parser import PARSER_VERSION, clean_email_html, parse_receipt_text
from subscriptions.tasks import parse_receipt_lead_task


User = get_user_model()


class ReceiptParserTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="receiptuser",
            email="receipt@example.com",
            password="Complex123!",
            is_active=True,
        )

    def _lead(self, **overrides):
        defaults = {
            "user": self.user,
            "message_id": "<receipt-1@example.com>",
            "sender": "billing@streambox.example",
            "sender_name": "StreamBox Billing",
            "subject": "Your StreamBox monthly receipt",
            "merchant_name": "StreamBox",
            "snippet": "Your monthly subscription receipt is ready.",
            "cleaned_body": "Total: $12.99\nBilling date: April 4, 2026\nNext billing date: May 4, 2026\nMonthly plan",
            "confidence_score": 80,
            "received_at": timezone.make_aware(datetime(2026, 4, 4, 12, 0, 0)),
        }
        defaults.update(overrides)
        return EmailSubscriptionLead.objects.create(**defaults)

    def test_parser_extracts_receipt_entities_from_messy_text(self):
        messy_text = """
        <html><body>
            <style>.hidden{display:none}</style>
            <h1>Receipt from StreamBox</h1>
            <p>Plan: Family Monthly Membership</p>
            <table><tr><td>Amount paid</td><td>$12.99</td></tr></table>
            Charged on: April 4, 2026<br>
            Your next renewal date: May 4, 2026
        </body></html>
        """

        extraction = parse_receipt_text(
            messy_text,
            subject="Your StreamBox monthly receipt",
            sender_name="StreamBox Billing",
            sender_email="billing@streambox.example",
        )

        self.assertEqual(extraction.merchant_name, "StreamBox")
        self.assertEqual(str(extraction.amount), "12.99")
        self.assertEqual(extraction.billing_date.isoformat(), "2026-04-04")
        self.assertEqual(extraction.likely_renewal_date.isoformat(), "2026-05-04")
        self.assertEqual(extraction.cadence, SubscriptionCandidate.CADENCE_MONTHLY)
        self.assertGreaterEqual(extraction.confidence_score, 80)
        self.assertEqual(extraction.parser_version, PARSER_VERSION)
        self.assertNotIn("<td>", extraction.raw_entity_metadata["cleaned_text"])

    def test_html_is_cleaned_to_plain_text_before_nlp_processing(self):
        cleaned = clean_email_html("<div>Total&nbsp;paid: <strong>$9.99</strong></div><script>bad()</script>")

        self.assertEqual(cleaned, "Total paid: $9.99")

    def test_task_stores_extracted_entities_as_pending_review_candidate(self):
        lead = self._lead()

        parse_receipt_lead_task.call_local(lead.id)

        candidate = SubscriptionCandidate.objects.get(user=self.user, source_email_lead=lead)
        self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_PENDING)
        self.assertEqual(candidate.source_type, SubscriptionCandidate.SOURCE_EMAIL_RECEIPT)
        self.assertEqual(candidate.merchant_name, "StreamBox")
        self.assertEqual(str(candidate.amount), "12.99")
        self.assertEqual(candidate.billing_date.isoformat(), "2026-04-04")
        self.assertEqual(candidate.likely_renewal_date.isoformat(), "2026-05-04")
        self.assertEqual(candidate.parser_version, PARSER_VERSION)
        self.assertIn("entities", candidate.raw_entity_metadata)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 0)

    def test_missing_fields_do_not_create_false_confirmed_subscriptions(self):
        lead = self._lead(
            message_id="<missing-amount@example.com>",
            cleaned_body="Thanks for your membership. Billing date: April 4, 2026. Monthly plan.",
        )

        parse_receipt_lead_task.call_local(lead.id)

        self.assertEqual(SubscriptionCandidate.objects.filter(user=self.user, source_email_lead=lead).count(), 0)
        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 0)

    def test_low_confidence_extraction_remains_review_only(self):
        lead = self._lead(
            message_id="<low-confidence@example.com>",
            sender="updates@example.com",
            sender_name="Updates",
            subject="Account notice",
            merchant_name="Updates",
            cleaned_body="Amount: $9.99\nBilling date: April 4, 2026\nMonthly",
            confidence_score=20,
        )

        parse_receipt_lead_task.call_local(lead.id)

        self.assertEqual(Subscription.objects.filter(user=self.user).count(), 0)
        candidate = SubscriptionCandidate.objects.filter(user=self.user, source_email_lead=lead).first()
        if candidate is not None:
            self.assertEqual(candidate.status, SubscriptionCandidate.STATUS_PENDING)
