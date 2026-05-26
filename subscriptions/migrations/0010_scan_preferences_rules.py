from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0009_emailscanpreference"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailscanpreference",
            name="email_selection_rules",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="emailscanpreference",
            name="scan_intervals",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
