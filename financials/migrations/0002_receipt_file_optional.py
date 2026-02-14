# Generated migration: make Receipt.file optional for manual material costs

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("financials", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="receipt",
            name="file",
            field=models.FileField(
                blank=True,
                help_text="Optional; you can add a material cost without a receipt.",
                null=True,
                upload_to="receipts/",
            ),
        ),
    ]
