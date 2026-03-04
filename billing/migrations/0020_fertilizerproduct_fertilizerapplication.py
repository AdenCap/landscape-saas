# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0001_initial'),
        ('customers', '0001_initial'),
        ('jobs', '0001_initial'),
        ('billing', '0019_googlemapsapiusage'),
    ]

    operations = [
        migrations.CreateModel(
            name='FertilizerProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Product name (e.g. 'Scotts Turf Builder 32-0-4')", max_length=200)),
                ('pricing_type', models.CharField(choices=[('per_pound', 'Per pound'), ('per_bag', 'Per bag')], default='per_pound', help_text='How this product is priced', max_length=20)),
                ('cost_per_pound', models.DecimalField(blank=True, decimal_places=2, help_text='Cost per pound (if pricing_type = per_pound)', max_digits=8, null=True)),
                ('cost_per_bag', models.DecimalField(blank=True, decimal_places=2, help_text='Cost per bag (if pricing_type = per_bag)', max_digits=8, null=True)),
                ('lbs_per_bag', models.DecimalField(blank=True, decimal_places=2, help_text='Pounds per bag (if pricing_type = per_bag)', max_digits=8, null=True)),
                ('active', models.BooleanField(default=True, help_text='Show in product selection dropdowns')),
                ('notes', models.TextField(blank=True, help_text='Optional notes about this product')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fertilizer_products', to='businesses.business')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('business', 'name')},
            },
        ),
        migrations.CreateModel(
            name='FertilizerApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('application_date', models.DateField(help_text='Date fertilizer was applied')),
                ('pounds_used', models.DecimalField(decimal_places=2, help_text='Total pounds of fertilizer applied', max_digits=10)),
                ('square_feet', models.DecimalField(blank=True, decimal_places=2, help_text='Square footage treated', max_digits=12, null=True)),
                ('lbs_per_1000_sqft', models.DecimalField(blank=True, decimal_places=3, help_text='Application rate (lbs per 1,000 sq ft)', max_digits=8, null=True)),
                ('material_cost', models.DecimalField(decimal_places=2, help_text='Cost of materials (calculated from product)', max_digits=10)),
                ('charge_amount', models.DecimalField(blank=True, decimal_places=2, help_text='Amount charged to customer (for profit calculation)', max_digits=10, null=True)),
                ('notes', models.TextField(blank=True, help_text='Optional notes about this application')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fertilizer_applications', to='businesses.business')),
                ('estimate', models.ForeignKey(blank=True, help_text='Estimate that led to this application (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fertilizer_applications', to='billing.estimate')),
                ('job', models.ForeignKey(blank=True, help_text='Job where this was applied (optional)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fertilizer_applications', to='jobs.job')),
                ('product', models.ForeignKey(blank=True, help_text='Product used (null if product was deleted)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applications', to='billing.fertilizerproduct')),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fertilizer_applications', to='customers.property')),
            ],
            options={
                'ordering': ['-application_date', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='fertilizerapplication',
            index=models.Index(fields=['property', 'application_date'], name='billing_fer_propert_idx'),
        ),
        migrations.AddIndex(
            model_name='fertilizerapplication',
            index=models.Index(fields=['business', 'application_date'], name='billing_fer_busines_idx'),
        ),
    ]
