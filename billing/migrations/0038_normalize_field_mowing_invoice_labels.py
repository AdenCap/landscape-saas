from django.db import migrations


def normalize_invoice_line_item_labels(apps, schema_editor):
    InvoiceLineItem = apps.get_model("billing", "InvoiceLineItem")
    for item in InvoiceLineItem.objects.filter(description__icontains="field mowing"):
        description = (item.description or "").strip()
        normalized = " ".join(description.lower().split())
        if normalized == "field mowing":
            item.description = "Mowing"
        elif normalized.startswith("field mowing - "):
            item.description = "Mowing" + description[len("Field Mowing"):]
        else:
            continue
        item.save(update_fields=["description"])


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0037_estimate_deposit_stripe_tracking"),
    ]

    operations = [
        migrations.RunPython(normalize_invoice_line_item_labels, migrations.RunPython.noop),
    ]
