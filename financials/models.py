from django.db import models
from django.conf import settings
from businesses.models import Business


class RevenueCategory(models.Model):
    """Owner-defined category for revenue breakdown (e.g. Mowing, Fertilizing, Mulching, Snow Removal)."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="revenue_categories",
    )
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0, help_text="Order in reports (lower first)")

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = [("business", "name")]

    def __str__(self):
        return self.name


def receipt_upload_to(instance, filename):
    """Store receipts by year/month."""
    from django.utils import timezone
    d = instance.receipt_date if instance.receipt_date else timezone.now().date()
    return f"receipts/{d.year}/{d.month:02d}/{filename}"


class Receipt(models.Model):
    """Receipt/expense record for bookkeeping and job material costs."""

    CATEGORY_CHOICES = [
        ("materials", "Materials"),
        ("fuel", "Fuel"),
        ("equipment", "Equipment / Rentals"),
        ("supplies", "Supplies"),
        ("labor", "Labor / Subcontractor"),
        ("other", "Other"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    file = models.FileField(upload_to=receipt_upload_to, blank=True, null=True, help_text="Optional; you can add a material cost without a receipt.")
    receipt_date = models.DateField(help_text="Date on the receipt")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total amount (for tracking material costs and taxes)",
    )
    vendor = models.CharField(max_length=255, blank=True, help_text="Store or vendor name")
    description = models.CharField(max_length=500, blank=True)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
        help_text="Link to a specific job (e.g. materials for this job)",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_receipts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-receipt_date", "-created_at"]

    def __str__(self):
        label = self.vendor or self.description or "Receipt"
        if self.amount is not None:
            return f"{label} — ${self.amount} ({self.receipt_date})"
        return f"{label} ({self.receipt_date})"


# ═══════════════════════════════════════════════
# Overhead & Business Cost Tracking
# ═══════════════════════════════════════════════

class OverheadExpense(models.Model):
    """Recurring overhead costs: rent, insurance, truck payments, software, etc."""
    FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
        ("weekly", "Weekly"),
    ]
    CATEGORY_CHOICES = [
        ("vehicle", "Vehicle Payment"),
        ("vehicle_insurance", "Vehicle Insurance"),
        ("equipment_payment", "Equipment Payment"),
        ("general_insurance", "General Liability Insurance"),
        ("rent", "Shop/Office Rent"),
        ("utilities", "Utilities"),
        ("software", "Software Subscriptions"),
        ("marketing", "Marketing/Advertising"),
        ("admin_salary", "Admin/Office Salary"),
        ("fuel", "Fuel (general)"),
        ("phone", "Phone/Internet"),
        ("license", "Licenses & Permits"),
        ("accounting", "Accounting/Bookkeeping"),
        ("other", "Other"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="overhead_expenses")
    name = models.CharField(max_length=200, help_text="e.g. F-250 truck payment, GL insurance, shop rent")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="other")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount per period")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} — ${self.amount}/{self.frequency}"

    @property
    def annual_cost(self):
        """Convert any frequency to annual cost."""
        multipliers = {"weekly": 52, "monthly": 12, "quarterly": 4, "annual": 1}
        return self.amount * multipliers.get(self.frequency, 12)

    @property
    def monthly_cost(self):
        return self.annual_cost / 12


class EquipmentAsset(models.Model):
    """Equipment with depreciation and cost tracking."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="equipment_assets")
    name = models.CharField(max_length=200, help_text="e.g. Scag V-Ride 52in, Stihl BR 800")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchase_date = models.DateField(null=True, blank=True)
    salvage_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text="Expected value at end of useful life")
    useful_life_hours = models.PositiveIntegerField(default=2500,
        help_text="Expected operating hours before replacement")
    annual_maintenance = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text="Estimated annual maintenance/repair cost")
    annual_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fuel_cost_per_hour = models.DecimalField(max_digits=6, decimal_places=2, default=0,
        help_text="Estimated fuel cost per operating hour")
    hours_per_year = models.PositiveIntegerField(default=1000,
        help_text="Estimated operating hours per year")
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def depreciation_per_hour(self):
        if self.useful_life_hours:
            return (self.purchase_price - self.salvage_value) / self.useful_life_hours
        return 0

    @property
    def cost_per_hour(self):
        """Total cost per operating hour: depreciation + maintenance + insurance + fuel."""
        maint_per_hour = self.annual_maintenance / self.hours_per_year if self.hours_per_year else 0
        ins_per_hour = self.annual_insurance / self.hours_per_year if self.hours_per_year else 0
        return self.depreciation_per_hour + maint_per_hour + ins_per_hour + self.fuel_cost_per_hour

    @property
    def annual_cost(self):
        return self.cost_per_hour * self.hours_per_year if self.hours_per_year else 0


class VehicleAsset(models.Model):
    """Vehicle with payment and cost tracking."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="vehicle_assets")
    name = models.CharField(max_length=200, help_text="e.g. 2022 Ford F-250, Crew cab truck")
    monthly_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_insurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    annual_registration = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    avg_mpg = models.DecimalField(max_digits=5, decimal_places=1, default=15,
        help_text="Average miles per gallon")
    fuel_price_per_gallon = models.DecimalField(max_digits=5, decimal_places=2, default=3.50)
    estimated_annual_miles = models.PositiveIntegerField(default=20000)
    annual_maintenance = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text="Estimated annual maintenance (oil, tires, repairs)")
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def annual_fuel_cost(self):
        if self.avg_mpg:
            return (self.estimated_annual_miles / self.avg_mpg) * self.fuel_price_per_gallon
        return 0

    @property
    def annual_cost(self):
        return (
            (self.monthly_payment * 12)
            + self.annual_insurance
            + self.annual_registration
            + self.annual_fuel_cost
            + self.annual_maintenance
        )

    @property
    def cost_per_mile(self):
        if self.estimated_annual_miles:
            return self.annual_cost / self.estimated_annual_miles
        return 0


class LaborBurdenConfig(models.Model):
    """Optional labor burden configuration — only the fields the owner fills in get used."""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="labor_burden")

    # All rates are percentages of base wage — ALL OPTIONAL
    fica_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="FICA/Social Security (typically 7.65%)")
    futa_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Federal unemployment tax (typically 0.6%)")
    suta_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="State unemployment tax (varies 2-5%)")
    workers_comp_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Workers comp rate (landscaping avg ~4.4%)")
    health_insurance_per_employee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Monthly health insurance cost per employee (flat $, not %)")
    pto_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="PTO accrual as % of wages (typically 3-8%)")
    other_burden_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Any other burden (uniforms, training, etc.)")

    def total_burden_pct(self):
        """Sum of all percentage-based burden components that are filled in."""
        total = 0
        for field in [self.fica_rate, self.futa_rate, self.suta_rate,
                      self.workers_comp_rate, self.pto_rate, self.other_burden_rate]:
            if field:
                total += field
        return total

    def __str__(self):
        return f"Labor burden for {self.business.name}: {self.total_burden_pct()}%"
