from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0008_email_lead_classification_and_scan_states"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailScanPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scan_scope",
                    models.CharField(
                        choices=[
                            ("receipts_only", "Receipts only"),
                            ("billing_mail", "Billing mail"),
                        ],
                        default="receipts_only",
                        max_length=30,
                    ),
                ),
                ("retention_period_days", models.PositiveIntegerField(default=180)),
                ("automatic_scans", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_scan_preference",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["user_id"],
            },
        ),
    ]
