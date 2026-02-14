# Generated for material/labor costs on line items

from django.db import migrations, models


def populate_labor_from_unit_price(apps, schema_editor):
    """Populate labor_cost from quantity*unit_price for existing line items."""
    InvoiceLineItem = apps.get_model("billing", "InvoiceLineItem")
    EstimateLineItem = apps.get_model("billing", "EstimateLineItem")
    for item in InvoiceLineItem.objects.filter(material_cost=0, labor_cost=0):
        item.labor_cost = item.quantity * item.unit_price
        item.save(update_fields=["labor_cost"])
    for item in EstimateLineItem.objects.filter(material_cost=0, labor_cost=0):
        item.labor_cost = item.quantity * item.unit_price
        item.save(update_fields=["labor_cost"])


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_estimate_view_token_accepted'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicelineitem',
            name='material_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of materials for this line',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='invoicelineitem',
            name='labor_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of labor for this line',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='estimatelineitem',
            name='material_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of materials for this line',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='estimatelineitem',
            name='labor_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Cost of labor for this line',
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name='estimatelineitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(populate_labor_from_unit_price, migrations.RunPython.noop),
    ]
