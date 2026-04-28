from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("billing", "0035_invoice_line_item_payment_tracking"),
        ("businesses", "0038_add_shop_address"),
        ("customers", "0016_add_contract_line_items"),
    ]

    operations = [
        migrations.AddField(
            model_name="promotion",
            name="code",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Optional promo code customers mention at signup.",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="invoicelineitem",
            name="is_discount",
            field=models.BooleanField(
                default=False,
                help_text="This line item represents an applied discount or promotion.",
            ),
        ),
        migrations.AddField(
            model_name="invoicelineitem",
            name="promotion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invoice_line_items",
                to="billing.promotion",
            ),
        ),
        migrations.CreateModel(
            name="PromotionRedemption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("code_used", models.CharField(blank=True, max_length=50)),
                ("redeemed_at", models.DateTimeField(auto_now_add=True)),
                ("notes", models.TextField(blank=True)),
                (
                    "business",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotion_redemptions", to="businesses.business"),
                ),
                (
                    "customer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotion_redemptions", to="customers.customer"),
                ),
                (
                    "invoice",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promotion_redemptions", to="billing.invoice"),
                ),
                (
                    "promotion",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="redemptions", to="billing.promotion"),
                ),
                (
                    "redeemed_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="promotion_redemptions_recorded", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-redeemed_at"]},
        ),
    ]
