from decimal import Decimal

from django.conf import settings
from django.core import signing
from django.db import models


EMAIL_TOKEN_SALT = "subscriptions.email_connection_token"


def _encrypt_email_token(value):
    if not value:
        return ""
    if value.startswith("signed:"):
        return value
    return "signed:" + signing.dumps(value, salt=EMAIL_TOKEN_SALT)


def _decrypt_email_token(value):
    if not value:
        return ""
    try:
        if value.startswith("signed:"):
            return signing.loads(value.removeprefix("signed:"), salt=EMAIL_TOKEN_SALT)
    except signing.BadSignature:
        pass
    return value


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
    STATUS_QUEUED = "queued"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_CHOICES = [
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_IN_PROGRESS, "In progress"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email_connection = models.ForeignKey(
        "EmailConnection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scan_runs",
    )
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


class EmailConnection(models.Model):
    PROVIDER_GMAIL = "gmail"
    PROVIDER_CHOICES = [
        (PROVIDER_GMAIL, "Gmail"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_DISCONNECTED = "disconnected"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_DISCONNECTED, "Disconnected"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_connections")
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    email_address = models.EmailField()
    scopes = models.JSONField(default=list, blank=True)
    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "email_address", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "provider", "email_address"], name="uniq_email_connection_per_user"),
        ]

    def save(self, *args, **kwargs):
        self.access_token = _encrypt_email_token(self.access_token)
        self.refresh_token = _encrypt_email_token(self.refresh_token)
        super().save(*args, **kwargs)

    def decrypted_access_token(self):
        return _decrypt_email_token(self.access_token)

    def decrypted_refresh_token(self):
        return _decrypt_email_token(self.refresh_token)


class EmailSubscriptionLead(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]
    CLASSIFICATION_BILLING_SIGNAL = "billing_signal"
    CLASSIFICATION_NEWSLETTER = "newsletter"
    CLASSIFICATION_MARKETING = "marketing"
    CLASSIFICATION_LOW_CONFIDENCE = "low_confidence"
    CLASSIFICATION_UNKNOWN = "unknown"
    CLASSIFICATION_CHOICES = [
        (CLASSIFICATION_BILLING_SIGNAL, "Billing signal"),
        (CLASSIFICATION_NEWSLETTER, "Newsletter"),
        (CLASSIFICATION_MARKETING, "Marketing"),
        (CLASSIFICATION_LOW_CONFIDENCE, "Low confidence"),
        (CLASSIFICATION_UNKNOWN, "Unknown"),
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
    cleaned_body = models.TextField(blank=True, default="")
    received_at = models.DateTimeField()
    confidence_score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    classification = models.CharField(
        max_length=30,
        choices=CLASSIFICATION_CHOICES,
        default=CLASSIFICATION_UNKNOWN,
    )
    classification_reason = models.TextField(blank=True, default="")
    last_action = models.CharField(max_length=50, blank=True, default="")
    last_action_at = models.DateTimeField(null=True, blank=True)
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

    SOURCE_TRANSACTIONS = "transactions"
    SOURCE_EMAIL_RECEIPT = "email_receipt"
    SOURCE_CHOICES = [
        (SOURCE_TRANSACTIONS, "Transactions"),
        (SOURCE_EMAIL_RECEIPT, "Email receipt"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_TRANSACTIONS)
    source_email_lead = models.ForeignKey(
        EmailSubscriptionLead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_candidates",
    )
    merchant_name = models.CharField(max_length=255)
    normalized_vendor = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    cadence = models.CharField(max_length=20, choices=CADENCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source_transaction_ids = models.JSONField(default=list)
    billing_date = models.DateField(null=True, blank=True)
    likely_renewal_date = models.DateField(null=True, blank=True)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    detection_reason = models.TextField(blank=True, default="")
    evidence_count = models.PositiveIntegerField(default=0)
    first_charge_date = models.DateField(null=True, blank=True)
    latest_charge_date = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    review_notes = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    parser_version = models.CharField(max_length=50, blank=True, default="")
    raw_entity_metadata = models.JSONField(default=dict, blank=True)
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
