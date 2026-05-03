from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0038_normalize_field_mowing_invoice_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimate",
            name="accepted_optional_item_ids",
            field=models.JSONField(
                blank=True,
                help_text="EstimateLineItem IDs for optional add-ons selected at acceptance. Null means legacy unknown.",
                null=True,
            ),
        ),
    ]
