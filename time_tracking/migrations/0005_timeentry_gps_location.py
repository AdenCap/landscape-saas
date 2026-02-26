# Generated migration for adding GPS location tracking to TimeEntry

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('time_tracking', '0004_schedule_change_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='timeentry',
            name='clock_in_latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='GPS latitude at clock-in (optional)',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='clock_in_longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='GPS longitude at clock-in (optional)',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='clock_out_latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='GPS latitude at clock-out (optional)',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='timeentry',
            name='clock_out_longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=7,
                help_text='GPS longitude at clock-out (optional)',
                max_digits=10,
                null=True,
            ),
        ),
    ]
