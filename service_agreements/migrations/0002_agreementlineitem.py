from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("service_agreements", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgreementLineItem",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("service_name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("frequency", models.CharField(choices=[("per_visit", "Per Visit"), ("monthly", "Monthly"), ("quarterly", "Quarterly"), ("seasonal", "Seasonal (Spring/Fall)"), ("annual", "Annual (Once)"), ("as_needed", "As Needed")], default="per_visit", max_length=20)),
                ("quantity", models.DecimalField(decimal_places=2, default=1, max_digits=8)),
                ("unit", models.CharField(blank=True, max_length=30)),
                ("unit_price", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("annual_total", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("times_completed", models.PositiveSmallIntegerField(default=0)),
                ("times_expected", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("agreement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="line_items", to="service_agreements.serviceagreement")),
            ],
            options={"ordering": ["order", "id"]},
        ),
    ]
