from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0041_business_website_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="default_invoice_card_payments_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Default whether newly created invoices allow client card checkout. Owners can still override each invoice.",
            ),
        ),
    ]
