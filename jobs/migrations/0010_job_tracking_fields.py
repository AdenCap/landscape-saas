# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0015_add_completed_by_and_completed_at'),  # Update if newer migrations exist
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='technician_latitude',
            field=models.DecimalField(blank=True, decimal_places=7, help_text='Current technician location (for customer tracking)', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='job',
            name='technician_longitude',
            field=models.DecimalField(blank=True, decimal_places=7, help_text='Current technician location (for customer tracking)', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='job',
            name='technician_location_updated_at',
            field=models.DateTimeField(blank=True, help_text='Last time technician location was updated', null=True),
        ),
        migrations.AddField(
            model_name='job',
            name='estimated_arrival_time',
            field=models.DateTimeField(blank=True, help_text='Estimated arrival time shown to customer', null=True),
        ),
    ]
