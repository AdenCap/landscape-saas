# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0010_customer_google_review_attempts_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='portal_access_token',
            field=models.CharField(blank=True, help_text='Secure token for customer portal access (auto-generated)', max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='portal_enabled',
            field=models.BooleanField(default=True, help_text='Allow customer to access their portal'),
        ),
    ]
