# Generated manually for estimate follow-up setting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0006_crews_colors_coords'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='estimate_follow_up_days',
            field=models.PositiveIntegerField(blank=True, default=0, help_text='Send automatic follow-up X days after estimate sent (0 = manual only)'),
        ),
    ]
