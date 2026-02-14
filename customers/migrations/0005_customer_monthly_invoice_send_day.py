# Generated migration: Customer monthly invoice send day

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0004_customer_invoice_frequency"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="monthly_invoice_send_day",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="For monthly clients: day of month to send the invoice (1–28). E.g. 1 = 1st, 15 = 15th. Leave blank to send manually.",
                null=True,
                validators=[MinValueValidator(1), MaxValueValidator(28)],
            ),
        ),
    ]
