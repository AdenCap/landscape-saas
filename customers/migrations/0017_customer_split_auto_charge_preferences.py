from django.db import migrations, models


def copy_legacy_auto_charge(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    Customer.objects.filter(auto_charge=True).update(
        auto_charge_completed_jobs=True,
        auto_charge_monthly_invoices=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0016_add_contract_line_items"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="auto_charge_completed_jobs",
            field=models.BooleanField(default=False, help_text="Automatically charge the saved card when a per-service job invoice is sent after completion."),
        ),
        migrations.AddField(
            model_name="customer",
            name="auto_charge_monthly_invoices",
            field=models.BooleanField(default=False, help_text="Automatically charge the saved card when a monthly invoice is sent."),
        ),
        migrations.RunPython(copy_legacy_auto_charge, migrations.RunPython.noop),
    ]
