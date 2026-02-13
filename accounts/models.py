from django.contrib.auth.models import AbstractUser
from django.db import models
from businesses.models import Business


class User(AbstractUser):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('crew', 'Crew'),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,  # Owner can be null initially if needed
        blank=True
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='crew')
    hourly_rate = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Hourly cost for crew members (used for labor cost reporting)'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

