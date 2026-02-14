# Generated migration: RevenueCategory for revenue breakdown

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0002_business_auto_invoice"),
        ("financials", "0002_receipt_file_optional"),
    ]

    operations = [
        migrations.CreateModel(
            name="RevenueCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("sort_order", models.PositiveIntegerField(default=0, help_text="Order in reports (lower first)")),
                ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revenue_categories", to="businesses.business")),
            ],
            options={
                "ordering": ["sort_order", "name"],
                "unique_together": {("business", "name")},
            },
        ),
    ]
