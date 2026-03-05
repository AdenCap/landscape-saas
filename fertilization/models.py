import builtins

from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class FertilizationProgram(models.Model):
    """Reusable annual fertilization program template."""

    GRASS_TYPE_CHOICES = [
        ('cool_season', 'Cool Season'),
        ('warm_season', 'Warm Season'),
        ('both', 'Both'),
    ]

    business = models.ForeignKey(
        'businesses.Business',
        on_delete=models.CASCADE,
        related_name='fertilization_programs',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    grass_type = models.CharField(
        max_length=20,
        choices=GRASS_TYPE_CHOICES,
        default='both',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['business', 'name']]

    def __str__(self):
        return f"{self.name}"

    @property
    def num_rounds(self):
        return self.rounds.count()


class ProgramRound(models.Model):
    """One round in a fertilization program template."""

    program = models.ForeignKey(
        FertilizationProgram,
        on_delete=models.CASCADE,
        related_name='rounds',
    )
    round_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    target_month_start = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    target_month_end = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    products = models.ManyToManyField(
        'billing.FertilizerProduct',
        blank=True,
    )
    default_rate_override = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    crew_instructions = models.TextField(blank=True)

    class Meta:
        ordering = ['program', 'round_number']
        unique_together = [['program', 'round_number']]

    def __str__(self):
        return f"R{self.round_number}: {self.name}"


class CustomerProgramEnrollment(models.Model):
    """Assigns a fertilization program to a property for a specific year."""

    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    PRICING_METHOD_CHOICES = [
        ('per_application', 'Per Application'),
        ('annual_flat', 'Annual Flat'),
        ('per_sqft', 'Per Sq Ft'),
    ]

    business = models.ForeignKey(
        'businesses.Business',
        on_delete=models.CASCADE,
        related_name='program_enrollments',
    )
    property = models.ForeignKey(
        'customers.Property',
        on_delete=models.CASCADE,
        related_name='program_enrollments',
    )
    program = models.ForeignKey(
        FertilizationProgram,
        on_delete=models.PROTECT,
        related_name='enrollments',
    )
    year = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='enrolled',
    )
    pricing_method = models.CharField(
        max_length=20,
        choices=PRICING_METHOD_CHOICES,
        default='per_application',
    )
    price_per_application = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    price_per_sqft = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
    )
    base_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
    )
    markup_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=40,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', 'property__address']
        unique_together = [['property', 'program', 'year']]

    def __str__(self):
        return f"{self.property.address} — {self.program.name} ({self.year})"

    @builtins.property
    def rounds_completed(self):
        return self.scheduled_rounds.filter(status='completed').count()

    @builtins.property
    def total_rounds(self):
        return self.scheduled_rounds.count()


class ScheduledRound(models.Model):
    """Actual scheduled round for an enrolled customer."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]

    enrollment = models.ForeignKey(
        CustomerProgramEnrollment,
        on_delete=models.CASCADE,
        related_name='scheduled_rounds',
    )
    round_template = models.ForeignKey(
        ProgramRound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_instances',
    )
    round_number = models.PositiveSmallIntegerField()
    scheduled_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fertilization_rounds',
    )
    application = models.ForeignKey(
        'billing.FertilizerApplication',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_round',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    material_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['enrollment', 'round_number']

    def __str__(self):
        return f"Round {self.round_number} — {self.enrollment.property.address} ({self.scheduled_date})"
