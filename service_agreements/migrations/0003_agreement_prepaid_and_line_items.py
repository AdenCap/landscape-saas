from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("service_agreements", "0002_agreementlineitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="serviceagreement",
            name="prepaid",
            field=models.BooleanField(default=False, help_text="Client paid upfront. Skip auto-invoicing for covered services."),
        ),
        migrations.AddField(
            model_name="serviceagreement",
            name="prepaid_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
