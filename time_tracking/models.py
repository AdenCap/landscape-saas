from django.conf import settings
from django.db import models


class TimeEntry(models.Model):
    """Records clock in/out punches for employees."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)

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
