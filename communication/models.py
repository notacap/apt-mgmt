from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        MAINTENANCE_REQUEST = "MAINTENANCE_REQUEST", "Maintenance Request"
        RENT_PAYMENT = "RENT_PAYMENT", "Rent Payment"
        MESSAGE = "MESSAGE", "Message"
        LEASE_EXPIRATION = "LEASE_EXPIRATION", "Lease Expiration"
        WORK_ASSIGNMENT = "WORK_ASSIGNMENT", "Work Assignment"
        GENERAL = "GENERAL", "General"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional fields for linking to specific objects
    link_url = models.URLField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"
