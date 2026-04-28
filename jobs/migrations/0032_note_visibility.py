from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0031_backfill_mowing_job_recurring_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobnote",
            name="visibility",
            field=models.CharField(
                choices=[("crew", "Crew visible"), ("internal", "Internal only")],
                default="crew",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="propertynote",
            name="visibility",
            field=models.CharField(
                choices=[("crew", "Crew visible"), ("internal", "Internal only")],
                default="crew",
                max_length=12,
            ),
        ),
    ]
