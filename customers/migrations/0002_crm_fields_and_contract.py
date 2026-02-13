# Generated manually for CRM feature

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='alt_phone',
            field=models.CharField(blank=True, max_length=20, verbose_name='Alternate phone'),
        ),
        migrations.AddField(
            model_name='customer',
            name='address_line1',
            field=models.CharField(blank=True, max_length=255, verbose_name='Address'),
        ),
        migrations.AddField(
            model_name='customer',
            name='address_line2',
            field=models.CharField(blank=True, max_length=255, verbose_name='Address line 2'),
        ),
        migrations.AddField(
            model_name='customer',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='customer',
            name='state',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='customer',
            name='postal_code',
            field=models.CharField(blank=True, max_length=20, verbose_name='ZIP / Postal code'),
        ),
        migrations.AddField(
            model_name='customer',
            name='notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contract_type', models.CharField(choices=[('monthly', 'Monthly Maintenance'), ('seasonal', 'Seasonal'), ('one_time', 'One-time'), ('biweekly', 'Bi-weekly'), ('custom', 'Custom')], default='monthly', max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('pending', 'Pending'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, help_text='Contract value (optional)', max_digits=10, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contracts', to='customers.customer')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='property',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
