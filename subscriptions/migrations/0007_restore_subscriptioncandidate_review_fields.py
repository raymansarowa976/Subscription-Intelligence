from django.db import migrations, models


def add_missing_candidate_review_columns(apps, schema_editor):
    table_name = "subscriptions_subscriptioncandidate"
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    SubscriptionCandidate = apps.get_model("subscriptions", "SubscriptionCandidate")
    fields = [
        ("detection_reason", models.TextField(blank=True, default="")),
        ("evidence_count", models.PositiveIntegerField(default=0)),
        ("first_charge_date", models.DateField(null=True, blank=True)),
        ("latest_charge_date", models.DateField(null=True, blank=True)),
        ("rejection_reason", models.TextField(blank=True, default="")),
        ("review_notes", models.TextField(blank=True, default="")),
        ("reviewed_at", models.DateTimeField(null=True, blank=True)),
    ]

    for name, field in fields:
        if name in existing_columns:
            continue
        field.set_attributes_from_name(name)
        schema_editor.add_field(SubscriptionCandidate, field)


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0006_emailconnection_emailscanrun_email_connection"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_missing_candidate_review_columns, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="detection_reason",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="evidence_count",
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="first_charge_date",
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="latest_charge_date",
                    field=models.DateField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="rejection_reason",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="review_notes",
                    field=models.TextField(blank=True, default=""),
                ),
                migrations.AddField(
                    model_name="subscriptioncandidate",
                    name="reviewed_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]
