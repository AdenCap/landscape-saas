from django.db import models
from customers.models import Property
from accounts.models import User
from businesses.models import Business

from django.utils import timezone
from datetime import timedelta

from decimal import Decimal
from pricing.models import ServiceTemplate

DEFAULT_COLORS = [
    '#3b82f6', '#22c55e', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
]


class Crew(models.Model):
    """A crew of employees with a leader. Used for job assignment and calendar coloring."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='crews')
    name = models.CharField(max_length=100)
    crew_leader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_crews',
        limit_choices_to={'role': 'crew'}
    )
    members = models.ManyToManyField(
        User,
        blank=True,
        related_name='crew_memberships',
        limit_choices_to={'role': 'crew'}
    )
    color = models.CharField(max_length=7, default='#3b82f6', help_text='Hex color for calendar/route display')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Job(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='jobs'
    )

    scheduled_date = models.DateField(null=True, blank=True, help_text='Null = unscheduled (accepted but not yet on calendar)')
    scheduled_time = models.TimeField(null=True, blank=True, help_text='Optional start time for week/day view')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
        help_text='Assign to individual employee'
    )
    assigned_crew = models.ForeignKey(
        Crew,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
        help_text='Or assign to a crew'
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    route_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.property.address} - {self.scheduled_date or 'Unscheduled'}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class JobServiceItem(models.Model):
        job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="service_items")
        service = models.ForeignKey(ServiceTemplate, on_delete=models.PROTECT)

        description = models.CharField(max_length=255, blank=True)  # optional override label
        quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))

        # Snapshot pricing used for this job (copied from property override or template at time of adding)
        unit = models.CharField(max_length=20, default="visit")
        unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

        billed_invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billed_job_items",
        )
        billed_at = models.DateTimeField(null=True, blank=True)

        def line_total(self):
            return self.quantity * self.unit_price

        def __str__(self):
            return f"{self.job} - {self.service.name}"


class RecurringJob(models.Model):
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
    ]

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='recurring_jobs'
    )

    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES
    )

    start_date = models.DateField()
    active = models.BooleanField(default=True)

    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_crew = models.ForeignKey(Crew, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_jobs')

    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.property.address} ({self.frequency})"

