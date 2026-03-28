from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0024_job_started_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="scheduled_end_time",
            field=models.TimeField(blank=True, null=True, help_text="Optional end time — set by calendar resize"),
        ),
    ]
