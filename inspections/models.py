from django.conf import settings
from django.db import models
from businesses.models import Business


class InspectionTemplate(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="inspection_templates")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sections = models.JSONField(
        default=list, blank=True,
        help_text='List of section dicts: [{"title": "...", "fields": [{"label": "...", "type": "pass_fail|text|number|photo"}]}]',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Inspection(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="inspections")
    job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections"
    )
    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections"
    )
    equipment = models.ForeignKey(
        "equipment.Equipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    findings = models.JSONField(
        default=dict, blank=True,
        help_text="Filled-in inspection data matching template sections.",
    )
    recommendations = models.TextField(blank=True)
    customer_visible = models.BooleanField(default=False, help_text="Share with customer via portal.")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        tpl = self.template.name if self.template else "Custom"
        return f"Inspection ({tpl}) — {self.status}"
