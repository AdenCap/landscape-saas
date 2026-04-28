from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0034_add_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicelineitem",
            name="is_paid",
            field=models.BooleanField(
                default=False,
                help_text="Whether this specific invoice line item has been paid.",
            ),
        ),
        migrations.AddField(
            model_name="invoicelineitem",
            name="paid_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When this line item was marked paid.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="invoicelineitem",
            name="paid_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_line_items_marked_paid",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="invoicelineitem",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not specified"),
                    ("card", "Credit/Debit Card"),
                    ("cash", "Cash"),
                    ("check", "Check"),
                    ("venmo", "Venmo"),
                    ("zelle", "Zelle"),
                    ("cashapp", "Cash App"),
                    ("paypal", "PayPal"),
                    ("ach", "ACH/Bank Transfer"),
                    ("other", "Other"),
                ],
                default="",
                help_text="How the client paid this specific line item.",
                max_length=20,
            ),
        ),
    ]
