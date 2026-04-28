from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0032_note_visibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobserviceitem",
            name="detail_description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Optional detailed description shown below the service name on job and invoice line items.",
            ),
        ),
    ]
