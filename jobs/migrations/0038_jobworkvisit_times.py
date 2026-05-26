from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0037_jobdayassignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobworkvisit",
            name="scheduled_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jobworkvisit",
            name="scheduled_end_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
