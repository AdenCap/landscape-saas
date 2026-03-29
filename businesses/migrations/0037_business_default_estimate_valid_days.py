from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0036_business_default_fert_price_per_sqft"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="default_estimate_valid_days",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Default number of days an estimate is valid for.",
            ),
        ),
    ]
