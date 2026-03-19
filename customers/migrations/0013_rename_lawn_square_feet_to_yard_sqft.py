# Rename lawn_square_feet → yard_sqft and update field attributes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0012_property_lawn_square_feet'),
    ]

    operations = [
        migrations.RenameField(
            model_name='property',
            old_name='lawn_square_feet',
            new_name='yard_sqft',
        ),
        migrations.AlterField(
            model_name='property',
            name='yard_sqft',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Yard sq ft',
                help_text='Lawn square footage. Used to auto-calculate fertilizer quantities and per-sqft pricing.',
            ),
        ),
    ]
