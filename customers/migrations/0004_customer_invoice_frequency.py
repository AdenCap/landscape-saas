# Generated migration: Customer invoice frequency (per service vs monthly)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0003_crews_colors_coords"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="invoice_frequency",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Ask each time (choose when job is completed)"),
                    ("per_service", "Per service — invoice when each job is completed"),
                    ("monthly", "Monthly — add completed jobs to a monthly invoice"),
                ],
                default="",
                help_text="When to send invoices for this client. Leave blank to choose per job.",
                max_length=20,
            ),
        ),
    ]
