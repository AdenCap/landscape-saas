from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_alter_auditlog_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("owner", "Owner"), ("manager", "Manager"), ("crew", "Crew")],
                default="crew",
                max_length=10,
            ),
        ),
    ]
