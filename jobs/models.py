# Add JobTemplate model at the end of the file
class JobTemplate(models.Model):
    """Reusable job templates for common services."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='job_templates'
    )
    name = models.CharField(max_length=255, help_text="Template name (e.g. 'Standard Lawn Care')")
    description = models.TextField(blank=True, help_text="Template description/notes")
    default_duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated duration in minutes"
    )
    service_items = models.JSONField(
        default=list,
        blank=True,
        help_text="List of service items with quantities: [{'service_id': 1, 'quantity': 1}]"
    )
    notes_template = models.TextField(
        blank=True,
        help_text="Default notes to add when creating job from template"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
