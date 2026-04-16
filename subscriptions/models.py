from decimal import Decimal

from django.conf import settings
from django.db import models


class TransactionImportRun(models.Model):
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50)
    account_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCEEDED)
    requested_transaction_count = models.PositiveIntegerField(default=0)
    ingested_transactions = models.PositiveIntegerField(default=0)
    duplicate_transactions = models.PositiveIntegerField(default=0)
    invalid_transactions = models.PositiveIntegerField(default=0)
    error_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class EmailScanRun(models.Model):
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50, default="imap")
    mailbox = models.CharField(max_length=100, default="INBOX")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCEEDED)
    scanned_message_count = models.PositiveIntegerField(default=0)
    matched_message_count = models.PositiveIntegerField(default=0)
    error_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class EmailSubscriptionLead(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    scan_run = models.ForeignKey(
        EmailScanRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    message_id = models.CharField(max_length=255)
    sender = models.CharField(max_length=255)
    sender_name = models.CharField(max_length=255, blank=True, default="")
    subject = models.CharField(max_length=255)
    merchant_name = models.CharField(max_length=255)
    snippet = models.TextField(blank=True, default="")
    received_at = models.DateTimeField()
    confidence_score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    raw_headers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "message_id"], name="uniq_email_subscription_lead_per_user"),
        ]


class TransactionEvidence(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    import_run = models.ForeignKey(
        TransactionImportRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    provider = models.CharField(max_length=50)
    account_id = models.CharField(max_length=100)
    provider_transaction_id = models.CharField(max_length=150, unique=True)
    merchant_name = models.CharField(max_length=255)
    normalized_merchant_name = models.CharField(max_length=255, blank=True, default="")
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    posted_at = models.DateField()
    raw_payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at", "-id"]


class SubscriptionCandidate(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_REJECTED, "Rejected"),
    ]

    CADENCE_MONTHLY = "monthly"
    CADENCE_YEARLY = "yearly"
    CADENCE_CHOICES = [
        (CADENCE_MONTHLY, "Monthly"),
        (CADENCE_YEARLY, "Yearly"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    merchant_name = models.CharField(max_length=255)
    normalized_vendor = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    cadence = models.CharField(max_length=20, choices=CADENCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source_transaction_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    @property
    def cadence_label(self):
        return self.get_cadence_display()

    @property
    def formatted_amount(self):
        return f"${self.amount:.2f}"


class Subscription(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    CATEGORY_STREAMING = "streaming"
    CATEGORY_MUSIC = "music"
    CATEGORY_SOFTWARE = "software"
    CATEGORY_UTILITIES = "utilities"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_STREAMING, "Streaming"),
        (CATEGORY_MUSIC, "Music"),
        (CATEGORY_SOFTWARE, "Software"),
        (CATEGORY_UTILITIES, "Utilities"),
        (CATEGORY_OTHER, "Other"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    merchant_name = models.CharField(max_length=255)
    normalized_vendor = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="USD")
    cadence = models.CharField(max_length=20)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    next_renewal = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["merchant_name", "id"]
