# Generated manually for estimate client view and acceptance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_estimate_estimateimage_estimatelineitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='view_token',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='estimate',
            name='accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='estimate',
            name='accepted_total',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
