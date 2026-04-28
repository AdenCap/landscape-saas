from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0038_add_shop_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="client_card_payments_enabled",
            field=models.BooleanField(
                default=True,
                help_text="If enabled and Stripe is connected, clients can pay invoices and estimate deposits by credit card.",
            ),
        ),
    ]
