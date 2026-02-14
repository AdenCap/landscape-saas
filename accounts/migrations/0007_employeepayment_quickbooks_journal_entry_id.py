# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_employeepayment'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeepayment',
            name='quickbooks_journal_entry_id',
            field=models.CharField(blank=True, help_text='QuickBooks Journal Entry Id after sync', max_length=32, null=True),
        ),
    ]
