# Generated manually for estimate follow-up emails

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0009_add_mulch_mowing_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='last_follow_up_at',
            field=models.DateTimeField(blank=True, help_text='When a follow-up email was last sent', null=True),
        ),
    ]
