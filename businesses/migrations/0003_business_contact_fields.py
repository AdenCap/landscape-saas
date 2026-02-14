# Generated manually for business communication settings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0002_business_auto_invoice'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='from_email',
            field=models.EmailField(blank=True, help_text='Email address estimates and messages are sent from (e.g. info@yourbusiness.com)', max_length=254),
        ),
        migrations.AddField(
            model_name='business',
            name='contact_email',
            field=models.EmailField(blank=True, help_text='Email clients can use to reach you (shown in estimates/emails)', max_length=254),
        ),
        migrations.AddField(
            model_name='business',
            name='contact_phone',
            field=models.CharField(blank=True, help_text='Phone number clients can use to reach you (shown in estimates/emails)', max_length=20),
        ),
    ]
