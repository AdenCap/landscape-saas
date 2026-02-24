# Per-business platform fee % on invoice card payments (blank = use global default)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0016_stripe_subscription_connect'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='stripe_connect_application_fee_percent',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Platform fee % on invoice card payments for this business. Leave blank to use the global default (STRIPE_CONNECT_APPLICATION_FEE_PERCENT).',
                max_digits=5,
                null=True,
            ),
        ),
    ]
