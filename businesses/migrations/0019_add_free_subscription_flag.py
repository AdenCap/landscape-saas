# Generated migration: Add free subscription flag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0018_email_customization'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='subscription_is_free',
            field=models.BooleanField(
                default=False,
                help_text='If True, this business has free access to the platform (no subscription required). Use this for partners, beta testers, or special cases.',
            ),
        ),
    ]
