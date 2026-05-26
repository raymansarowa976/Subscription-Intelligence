import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0005_receipt_parser_candidate_metadata"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EmailConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(choices=[("gmail", "Gmail")], max_length=50),
                ),
                ("email_address", models.EmailField(max_length=254)),
                ("scopes", models.JSONField(blank=True, default=list)),
                ("access_token", models.TextField(blank=True, default="")),
                ("refresh_token", models.TextField(blank=True, default="")),
                ("token_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("disconnected", "Disconnected")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="email_connections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["provider", "email_address", "id"],
            },
        ),
        migrations.AddField(
            model_name="emailscanrun",
            name="email_connection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scan_runs",
                to="subscriptions.emailconnection",
            ),
        ),
        migrations.AddConstraint(
            model_name="emailconnection",
            constraint=models.UniqueConstraint(
                fields=("user", "provider", "email_address"),
                name="uniq_email_connection_per_user",
            ),
        ),
    ]
