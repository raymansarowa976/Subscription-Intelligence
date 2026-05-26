from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0010_scan_preferences_rules"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_currency", models.CharField(max_length=3)),
                ("to_currency", models.CharField(max_length=3)),
                ("rate", models.DecimalField(decimal_places=8, max_digits=18)),
                ("effective_date", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-effective_date", "from_currency", "to_currency"],
            },
        ),
        migrations.AddConstraint(
            model_name="exchangerate",
            constraint=models.UniqueConstraint(
                fields=("from_currency", "to_currency", "effective_date"),
                name="uniq_exchange_rate_currency_pair_per_day",
            ),
        ),
    ]
