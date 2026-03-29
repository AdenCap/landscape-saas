from django.conf import settings
from django.db import models
from businesses.models import Business


class ServiceAgreement(models.Model):
    AGREEMENT_TYPE_CHOICES = [
        ("maintenance", "Maintenance Plan"),
        ("warranty", "Extended Warranty"),
        ("service", "Service Contract"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]
    BILLING_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"),
        ("one_time", "One-Time"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="service_agreements")
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="service_agreements"
    )
    name = models.CharField(max_length=200)
    agreement_type = models.CharField(max_length=20, choices=AGREEMENT_TYPE_CHOICES, default="maintenance")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    billing_frequency = models.CharField(max_length=20, choices=BILLING_FREQUENCY_CHOICES, default="annual")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    auto_renew = models.BooleanField(default=False)
    visits_included = models.PositiveIntegerField(default=0, help_text="Number of visits included per term.")
    visits_used = models.PositiveIntegerField(default=0)
    discount_percent_on_repairs = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Discount % on repairs for agreement holders.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} — {self.customer}"

    @property
    def visits_remaining(self):
        return max(0, self.visits_included - self.visits_used)

    @property
    def is_active(self):
        from django.utils import timezone
        today = timezone.localdate()
        return self.status == "active" and self.start_date <= today and (not self.end_date or self.end_date >= today)


class AgreementVisit(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    agreement = models.ForeignKey(ServiceAgreement, on_delete=models.CASCADE, related_name="visits")
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="agreement_visits"
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_date"]

    def __str__(self):
        return f"Visit for {self.agreement} on {self.scheduled_date}"


class AgreementLineItem(models.Model):
    """Individual service included in a maintenance agreement with set pricing."""
    FREQUENCY_CHOICES = [
        ("per_visit", "Per Visit"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("seasonal", "Seasonal (Spring/Fall)"),
        ("annual", "Annual (Once)"),
        ("as_needed", "As Needed"),
    ]

    agreement = models.ForeignKey(
        ServiceAgreement, on_delete=models.CASCADE, related_name="line_items"
    )
    service_name = models.CharField(max_length=200, help_text="e.g. Mowing, Mulch, Spring Cleanup")
    description = models.TextField(blank=True, help_text="Details about what's included")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="per_visit")
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit = models.CharField(max_length=30, blank=True, help_text="e.g. visit, yard, application")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Total for the year if different from qty x price"
    )
    times_completed = models.PositiveSmallIntegerField(default=0)
    times_expected = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="How many times this should be done per year"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.service_name} — {self.agreement}"

    @property
    def line_total(self):
        if self.annual_total:
            return self.annual_total
        return self.quantity * self.unit_price

    @property
    def progress_display(self):
        if self.times_expected:
            return f"{self.times_completed}/{self.times_expected}"
        return ""

    @property
    def is_complete(self):
        return self.times_expected and self.times_completed >= self.times_expected
