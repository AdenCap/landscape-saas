"""Customer Satisfaction Surveys: Automated surveys after job completion."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job


class Survey(models.Model):
    """Customer satisfaction survey response."""
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='surveys'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='surveys'
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='surveys',
        help_text="Job this survey is for"
    )
    
    # Survey questions
    overall_satisfaction = models.PositiveSmallIntegerField(
        help_text="Overall satisfaction (1-5)",
        choices=[(i, i) for i in range(1, 6)]
    )
    quality_rating = models.PositiveSmallIntegerField(
        help_text="Quality of work (1-5)",
        choices=[(i, i) for i in range(1, 6)],
        null=True,
        blank=True
    )
    timeliness_rating = models.PositiveSmallIntegerField(
        help_text="Timeliness (1-5)",
        choices=[(i, i) for i in range(1, 6)],
        null=True,
        blank=True
    )
    communication_rating = models.PositiveSmallIntegerField(
        help_text="Communication (1-5)",
        choices=[(i, i) for i in range(1, 6)],
        null=True,
        blank=True
    )
    
    # Open-ended feedback
    what_went_well = models.TextField(blank=True, help_text="What went well?")
    what_could_improve = models.TextField(blank=True, help_text="What could be improved?")
    additional_comments = models.TextField(blank=True)
    
    # NPS
    would_recommend = models.BooleanField(
        null=True,
        blank=True,
        help_text="Would you recommend us to others?"
    )
    nps_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Net Promoter Score (0-10): How likely are you to recommend us?"
    )
    
    completed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-completed_at']
    
    def __str__(self):
        return f"{self.customer.name} - {self.overall_satisfaction}/5"
    
    @property
    def average_rating(self):
        """Calculate average of all ratings."""
        ratings = [self.overall_satisfaction]
        if self.quality_rating:
            ratings.append(self.quality_rating)
        if self.timeliness_rating:
            ratings.append(self.timeliness_rating)
        if self.communication_rating:
            ratings.append(self.communication_rating)
        return sum(ratings) / len(ratings) if ratings else 0
