from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0025_job_scheduled_end_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="schedule_by_date",
            field=models.DateField(blank=True, null=True, help_text="Target date to schedule this job by"),
        ),
    ]
