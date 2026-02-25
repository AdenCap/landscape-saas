"""Customer Reviews: Track customer reviews and ratings."""
from django.db import models
from django.conf import settings
from businesses.models import Business
from customers.models import Customer
from jobs.models import Job


class Review(models.Model):
    """Customer review/rating after job completion."""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]
    
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text="Job this review is for (if applicable)"
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Show this review publicly (on customer portal, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.name} - {self.rating} stars"
    
    @property
    def stars_display(self):
        return '★' * self.rating + '☆' * (5 - self.rating)
