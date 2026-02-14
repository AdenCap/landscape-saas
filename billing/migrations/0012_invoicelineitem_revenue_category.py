# Generated migration: add revenue_category to InvoiceLineItem

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0003_revenuecategory"),
        ("billing", "0011_invoice_quickbooks_invoice_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoicelineitem",
            name="revenue_category",
            field=models.ForeignKey(
                blank=True,
                help_text="For revenue breakdown (from service or manual).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_line_items",
                to="financials.revenuecategory",
            ),
        ),
    ]
