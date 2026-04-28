from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0039_business_client_card_payments_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="client_saved_cards_enabled",
            field=models.BooleanField(default=True, help_text="If enabled, owners can securely save authorized customer cards for future off-session charges."),
        ),
    ]
