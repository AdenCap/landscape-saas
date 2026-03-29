from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0037_business_default_estimate_valid_days"),
        ("customers", "0013_rename_lawn_square_feet_to_yard_sqft"),
        ("billing", "0031_add_view_tracking"),
    ]

    operations = [
        migrations.CreateModel(
            name="Promotion",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("promo_type", models.CharField(choices=[("percent_off", "Percentage Off"), ("fixed_off", "Fixed Amount Off"), ("buy_x_get_free", "Buy X Get 1 Free"), ("free_service", "Free Service"), ("custom", "Custom")], default="buy_x_get_free", max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("redeemed", "Redeemed"), ("expired", "Expired")], default="active", max_length=20)),
                ("discount_value", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("buy_quantity", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("free_quantity", models.PositiveSmallIntegerField(blank=True, default=1, null=True)),
                ("current_count", models.PositiveSmallIntegerField(default=0)),
                ("service_name", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("valid_from", models.DateField(blank=True, null=True)),
                ("valid_until", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to="businesses.business")),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="promotions", to="customers.customer")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
