# Generated manually for time tracking feature

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='hourly_rate',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Hourly cost for crew members (used for labor cost reporting)', max_digits=8, null=True),
        ),
    ]
