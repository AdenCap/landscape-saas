# Generated manually for estimates feature

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_invoice_period_end_invoice_period_start_and_more'),
        ('businesses', '0002_business_auto_invoice'),
        ('customers', '0002_crm_fields_and_contract'),
    ]

    operations = [
        migrations.CreateModel(
            name='Estimate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Landscape Service Estimate', max_length=255)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('sent', 'Sent'), ('accepted', 'Accepted'), ('declined', 'Declined')], default='draft', max_length=20)),
                ('valid_until', models.DateField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='estimates', to='businesses.business')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='estimates', to='customers.customer')),
            ],
        ),
        migrations.CreateModel(
            name='EstimateLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=500)),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=10)),
                ('unit', models.CharField(default='ea', max_length=50)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_addon', models.BooleanField(default=False, verbose_name='Optional add-on')),
                ('order', models.PositiveIntegerField(default=0)),
                ('estimate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='billing.estimate')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='EstimateImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='estimates/%Y/%m/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('estimate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='billing.estimate')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
    ]
