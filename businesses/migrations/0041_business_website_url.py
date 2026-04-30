from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0040_business_client_saved_cards_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="website_url",
            field=models.URLField(blank=True, help_text="Website shown on client-facing estimates and invoices"),
        ),
    ]
