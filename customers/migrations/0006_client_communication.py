# Generated migration: client communication preference and message history

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("customers", "0005_customer_monthly_invoice_send_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="communication_preference",
            field=models.CharField(
                blank=True,
                choices=[
                    ("email", "Email"),
                    ("sms", "Text (SMS)"),
                    ("both", "Email and Text"),
                ],
                default="",
                help_text="How this client prefers to be contacted.",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="ClientMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("email", "Email"), ("sms", "SMS")],
                        max_length=10,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("sent", "Sent"), ("received", "Received")],
                        max_length=10,
                    ),
                ),
                (
                    "subject",
                    models.CharField(
                        blank=True,
                        help_text="Email subject; blank for SMS.",
                        max_length=255,
                    ),
                ),
                ("body", models.TextField()),
                (
                    "to_address",
                    models.CharField(
                        blank=True,
                        help_text="Email address or phone number the message was sent to or received from.",
                        max_length=255,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="customers.customer",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="User who sent this message (null for received or system).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_client_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
