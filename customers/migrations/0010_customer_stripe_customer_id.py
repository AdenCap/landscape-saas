# Generated migration for adding stripe_customer_id to Customer model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0009_recurring_and_fertilization'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='stripe_customer_id',
            field=models.CharField(
                blank=True,
                help_text="Stripe Customer ID in the business's connected account. Used to store payment methods on file for recurring charges.",
                max_length=255,
            ),
        ),
    ]
