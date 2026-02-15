# Generated migration: job labor and material cost for profit tracking

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0009_job_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="labor_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal("0"),
                help_text="Labor cost for this job (used for profit reporting). Materials from linked receipts.",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="job",
            name="material_cost",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal("0"),
                help_text="Material cost for this job if not tracked via receipts.",
                max_digits=10,
            ),
        ),
    ]
