# Generated manually for Stripe subscription + Connect

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0015_payment_reminders_and_outstanding'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='stripe_customer_id',
            field=models.CharField(blank=True, help_text='Stripe Customer ID for this business (platform subscription).', max_length=255),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_subscription_id',
            field=models.CharField(blank=True, help_text='Stripe Subscription ID (recurring payment to platform).', max_length=255),
        ),
        migrations.AddField(
            model_name='business',
            name='subscription_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'No subscription'),
                    ('active', 'Active'),
                    ('trialing', 'Trialing'),
                    ('past_due', 'Past due'),
                    ('canceled', 'Canceled'),
                    ('unpaid', 'Unpaid'),
                ],
                default='',
                help_text='Current subscription status; active or trialing = can use the app.',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='business',
            name='subscription_current_period_end',
            field=models.DateTimeField(blank=True, help_text='When the current billing period ends (from Stripe).', null=True),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_connect_account_id',
            field=models.CharField(blank=True, help_text='Stripe Connect account ID so this business can accept invoice payments.', max_length=255),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_connect_charges_enabled',
            field=models.BooleanField(default=False, help_text='Whether the connected account can accept charges (set by webhook).'),
        ),
    ]
