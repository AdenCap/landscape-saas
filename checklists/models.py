from django.conf import settings
from django.db import models
from businesses.models import Business


class ChecklistTemplate(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="checklist_templates")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False, help_text="Auto-attach to new jobs.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ChecklistTemplateItem(models.Model):
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name="items")
    label = models.CharField(max_length=200)
    section = models.CharField(max_length=100, blank=True, help_text="Group header for this item.")
    requires_photo = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        return self.label


class JobChecklist(models.Model):
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="checklists")
    template = models.ForeignKey(
        ChecklistTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        tpl = self.template.name if self.template else "Custom"
        return f"Checklist ({tpl}) for Job #{self.job_id}"

    @property
    def progress(self):
        total = self.items.count()
        if total == 0:
            return 0
        done = self.items.filter(is_completed=True).count()
        return round(done / total * 100)


class JobChecklistItem(models.Model):
    checklist = models.ForeignKey(JobChecklist, on_delete=models.CASCADE, related_name="items")
    template_item = models.ForeignKey(
        ChecklistTemplateItem, on_delete=models.SET_NULL, null=True, blank=True
    )
    label = models.CharField(max_length=200)
    section = models.CharField(max_length=100, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    photo = models.ImageField(upload_to="checklist_photos/%Y/%m/", blank=True)
    notes = models.CharField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]

    def __str__(self):
        status = "done" if self.is_completed else "pending"
        return f"{self.label} [{status}]"
