from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0010_estimate_follow_up'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='quickbooks_invoice_id',
            field=models.CharField(blank=True, help_text='QuickBooks Online Invoice Id after push', max_length=32, null=True),
        ),
    ]
