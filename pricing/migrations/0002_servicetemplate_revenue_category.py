# Generated migration: add revenue_category to ServiceTemplate

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0003_revenuecategory"),
        ("pricing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicetemplate",
            name="revenue_category",
            field=models.ForeignKey(
                blank=True,
                help_text="Used for revenue breakdown in Financials (e.g. Mowing, Fertilizing).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="service_templates",
                to="financials.revenuecategory",
            ),
        ),
    ]
