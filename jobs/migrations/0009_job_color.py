# Generated for job color override

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0008_scheduled_date_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='color',
            field=models.CharField(
                blank=True,
                help_text='Override color for calendar (hex e.g. #3b82f6). Leave empty to use crew/employee default.',
                max_length=7,
                null=True,
            ),
        ),
    ]
