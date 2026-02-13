# Generated manually for logo support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0003_business_contact_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="logo",
            field=models.ImageField(
                blank=True,
                help_text="Logo shown on invoices, estimates, and emails sent to clients",
                null=True,
                upload_to="business_logos/%Y/",
            ),
        ),
    ]
