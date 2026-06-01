from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0042_business_default_invoice_card_payments_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="card_processing_fee_enabled",
            field=models.BooleanField(
                default=False,
                help_text="If enabled, client card checkout adds the configured processing fee on top of the invoice total.",
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="card_processing_fee_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("3.00"),
                help_text="Percentage added to client card checkout when card processing fees are enabled.",
                max_digits=5,
            ),
        ),
    ]
