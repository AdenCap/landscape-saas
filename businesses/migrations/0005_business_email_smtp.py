# Generated for per-business Gmail configuration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0004_business_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="email_smtp_user",
            field=models.EmailField(
                blank=True,
                help_text="Gmail address for sending estimates (e.g. your.business@gmail.com)",
                max_length=254,
            ),
        ),
        migrations.AddField(
            model_name="business",
            name="email_smtp_password",
            field=models.CharField(
                blank=True,
                help_text="Gmail App Password (not your normal password)",
                max_length=255,
            ),
        ),
    ]
