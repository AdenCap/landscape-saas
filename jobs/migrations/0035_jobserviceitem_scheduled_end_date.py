from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0034_normalize_field_mowing_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobserviceitem",
            name="scheduled_end_date",
            field=models.DateField(
                blank=True,
                help_text="Optional end date when this line item spans multiple days.",
                null=True,
            ),
        ),
    ]
