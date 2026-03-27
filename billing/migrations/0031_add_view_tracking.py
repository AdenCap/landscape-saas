from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0030_add_template_styles"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="first_viewed_at",
            field=models.DateTimeField(blank=True, null=True, help_text="First time the client opened this invoice"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="last_viewed_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Most recent time the client viewed this invoice"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="view_count",
            field=models.PositiveIntegerField(default=0, help_text="How many times the client has viewed this invoice"),
        ),
        migrations.AddField(
            model_name="estimate",
            name="first_viewed_at",
            field=models.DateTimeField(blank=True, null=True, help_text="First time the client opened this estimate"),
        ),
        migrations.AddField(
            model_name="estimate",
            name="last_viewed_at",
            field=models.DateTimeField(blank=True, null=True, help_text="Most recent time the client viewed this estimate"),
        ),
        migrations.AddField(
            model_name="estimate",
            name="view_count",
            field=models.PositiveIntegerField(default=0, help_text="How many times the client has viewed this estimate"),
        ),
    ]
