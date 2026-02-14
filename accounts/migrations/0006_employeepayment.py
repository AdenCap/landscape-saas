# Generated manually for EmployeePayment

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0001_initial'),
        ('accounts', '0005_crews_colors_coords'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeePayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('paid_date', models.DateField()),
                ('notes', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employee_payments', to='businesses.business')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-paid_date', '-created_at'],
            },
        ),
    ]
