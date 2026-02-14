from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('businesses', '0007_estimate_follow_up_days'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickBooksConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('realm_id', models.CharField(help_text='QuickBooks company ID', max_length=32)),
                ('access_token', models.CharField(max_length=512)),
                ('refresh_token', models.CharField(max_length=512)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quickbooks_connection', to='businesses.business')),
            ],
            options={
                'verbose_name': 'QuickBooks connection',
                'verbose_name_plural': 'QuickBooks connections',
            },
        ),
    ]
