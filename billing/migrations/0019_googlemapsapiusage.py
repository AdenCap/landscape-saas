# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0001_initial'),
        ('billing', '0018_document_templates_and_custom_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleMapsApiUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True, help_text='Date of API usage')),
                ('request_count', models.PositiveIntegerField(default=0, help_text='Number of API requests made on this date')),
                ('request_type', models.CharField(choices=[('directions', 'Directions API'), ('geocoding', 'Geocoding API'), ('javascript', 'Maps JavaScript API')], default='directions', help_text='Type of API request', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(blank=True, help_text='If set, tracks usage per business. If null, tracks global usage.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='google_maps_api_usage', to='businesses.business')),
            ],
            options={
                'ordering': ['-date'],
                'unique_together': {('business', 'date', 'request_type')},
            },
        ),
        migrations.AddIndex(
            model_name='googlemapsapiusage',
            index=models.Index(fields=['business', 'date', 'request_type'], name='billing_goo_busines_abc123_idx'),
        ),
        migrations.AddIndex(
            model_name='googlemapsapiusage',
            index=models.Index(fields=['date'], name='billing_goo_date_idx'),
        ),
    ]
