from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0035_jobserviceitem_scheduled_end_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobWorkVisit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheduled_date", models.DateField()),
                (
                    "scheduled_end_date",
                    models.DateField(
                        blank=True,
                        help_text="Optional end date when this return visit spans multiple days.",
                        null=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("completed", "Completed"),
                            ("skipped", "Skipped"),
                        ],
                        default="scheduled",
                        max_length=20,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_visits",
                        to="jobs.job",
                    ),
                ),
                (
                    "service_item",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional line item this return visit is for.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="work_visits",
                        to="jobs.jobserviceitem",
                    ),
                ),
            ],
            options={
                "ordering": ["scheduled_date", "id"],
            },
        ),
    ]
