from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0036_promotion_redemptions_and_invoice_discounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="estimate",
            name="stripe_deposit_checkout_session_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stripe Checkout Session ID for this estimate deposit payment.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="estimate",
            name="stripe_deposit_payment_intent_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stripe Payment Intent ID for this estimate deposit payment.",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="estimate",
            name="stripe_deposit_charge_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stripe Charge ID for this estimate deposit payment.",
                max_length=255,
                null=True,
            ),
        ),
    ]
