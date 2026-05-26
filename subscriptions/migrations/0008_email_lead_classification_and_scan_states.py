from django.db import migrations, models


def add_missing_lead_action_columns(apps, schema_editor):
    table_name = "subscriptions_emailsubscriptionlead"
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    EmailSubscriptionLead = apps.get_model("subscriptions", "EmailSubscriptionLead")
    fields = [
        (
            "classification",
            models.CharField(
                choices=[
                    ("billing_signal", "Billing signal"),
                    ("newsletter", "Newsletter"),
                    ("marketing", "Marketing"),
                    ("low_confidence", "Low confidence"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=30,
            ),
        ),
        ("classification_reason", models.TextField(blank=True, default="")),
        ("last_action", models.CharField(blank=True, default="", max_length=50)),
        ("last_action_at", models.DateTimeField(blank=True, null=True)),
    ]
    for name, field in fields:
        if name in existing_columns:
            continue
        field.set_attributes_from_name(name)
        schema_editor.add_field(EmailSubscriptionLead, field)


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0007_restore_subscriptioncandidate_review_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailscanrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("succeeded", "Succeeded"),
                    ("failed", "Failed"),
                    ("queued", "Queued"),
                    ("in_progress", "In progress"),
                ],
                default="succeeded",
                max_length=20,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_lead_action_columns, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="emailsubscriptionlead",
                    name="classification",
                    field=models.CharField(
                        choices=[
                            ("billing_signal", "Billing signal"),
                            ("newsletter", "Newsletter"),
                            ("marketing", "Marketing"),
                            ("low_confidence", "Low confidence"),
                            ("unknown", "Unknown"),
                        ],
                        default="unknown",
                        max_length=30,
                    ),
                ),
                migrations.AddField(
                    model_name="emailsubscriptionlead",
                    name="classification_reason",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="emailsubscriptionlead",
                    name="last_action",
                    field=models.CharField(blank=True, default="", max_length=50),
                ),
                migrations.AddField(
                    model_name="emailsubscriptionlead",
                    name="last_action_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
