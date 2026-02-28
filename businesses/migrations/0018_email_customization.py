# Email content customization for invoices and estimates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0017_stripe_connect_application_fee_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='invoice_email_subject',
            field=models.CharField(blank=True, help_text='Subject line when sending invoices by email. Use {{invoice_id}}, {{customer_name}}, {{business_name}}. Leave blank for default.', max_length=200),
        ),
        migrations.AddField(
            model_name='business',
            name='invoice_email_intro',
            field=models.TextField(blank=True, help_text='Opening line in the invoice email. Leave blank for default.'),
        ),
        migrations.AddField(
            model_name='business',
            name='invoice_email_closing',
            field=models.TextField(blank=True, help_text='Closing line before your contact info. Leave blank for default.'),
        ),
        migrations.AddField(
            model_name='business',
            name='estimate_email_subject',
            field=models.CharField(blank=True, help_text='Subject line when sending estimates. Use {{title}}, {{customer_name}}, {{business_name}}. Leave blank for default.', max_length=200),
        ),
        migrations.AddField(
            model_name='business',
            name='estimate_email_intro',
            field=models.TextField(blank=True, help_text='Opening line in the estimate email. Leave blank for default.'),
        ),
        migrations.AddField(
            model_name='business',
            name='estimate_email_closing',
            field=models.TextField(blank=True, help_text='Closing line in the estimate email. Leave blank for default.'),
        ),
        migrations.AddField(
            model_name='business',
            name='estimate_followup_email_subject',
            field=models.CharField(blank=True, help_text='Subject line for estimate follow-up emails. Leave blank for default.', max_length=200),
        ),
        migrations.AddField(
            model_name='business',
            name='estimate_followup_email_intro',
            field=models.TextField(blank=True, help_text='Opening line in the estimate follow-up email. Leave blank for default.'),
        ),
    ]
