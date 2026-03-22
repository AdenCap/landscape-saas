from django.conf import settings
from django.db import models


class TimeOffRequest(models.Model):
    """Employee request for time off (vacation, sick, personal). Owner approves or denies."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]
    TYPE_CHOICES = [
        ("vacation", "Vacation"),
        ("sick", "Sick"),
        ("personal", "Personal"),
        ("other", "Other"),
    ]
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="time_off_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="time_off_requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="vacation")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="time_off_reviews",
    )

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}: {self.start_date}–{self.end_date} ({self.get_status_display()})"


class EmployeeSchedule(models.Model):
    """Recurring weekly schedule: which days and times an employee typically works."""
    DAYS = [(i, d) for i, d in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_slots",
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS)  # 0=Monday, 6=Sunday
    start_time = models.TimeField(null=True, blank=True)  # null = day off or "all day"
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["user", "day_of_week"]
        unique_together = [["user", "day_of_week"]]

    def __str__(self):
        if self.start_time and self.end_time:
            return f"{self.user.username} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
        return f"{self.user.username} {self.get_day_of_week_display()} (off)"


class ScheduleChangeLog(models.Model):
    """Audit: who changed employee schedule (weekly slots) and when."""
    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="schedule_change_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_changes_made",
    )
    target_user_id = models.PositiveIntegerField(null=True, blank=True, help_text="Employee whose schedule was edited")
    details = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TimeEntry(models.Model):
    """Records clock in/out punches for employees. Owner approval required before counting for pay."""
    STATUS_CHOICES = [
        ("pending_approval", "Pending approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)
    clock_in_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_in_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    clock_out_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending_approval",
        help_text="Only approved entries count for payroll.",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="time_entries_approved",
    )

    class Meta:
        ordering = ['-clock_in']
        verbose_name_plural = 'Time entries'

    def __str__(self):
        status = 'Clocked in' if self.clock_out is None else 'Clocked out'
        return f"{self.user.username} - {self.clock_in.date()} {status}"

    @property
    def duration_minutes(self):
        """Returns duration in minutes, or None if still clocked in."""
        if self.clock_out is None:
            return None
        delta = self.clock_out - self.clock_in
        return int(delta.total_seconds() / 60)

    @property
    def duration_display(self):
        """Returns formatted duration like '2h 30m'."""
        m = self.duration_minutes
        if m is None:
            return "In progress"
        return f"{m // 60}h {m % 60}m"
