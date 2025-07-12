from django.contrib.auth.models import AbstractUser
from django.db import models
from properties.models import Company, Property
import uuid

class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERUSER = "SUPERUSER", "Superuser"
        LANDLORD = "LANDLORD", "Landlord"
        EMPLOYEE = "EMPLOYEE", "Employee"
        TENANT = "TENANT", "Tenant"

    role = models.CharField(max_length=50, choices=Role.choices)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="users", null=True, blank=True)
    property = models.ForeignKey(Property, on_delete=models.SET_NULL, related_name="users", null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Invitation(models.Model):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, choices=User.Role.choices)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invitations", null=True, blank=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="invitations", null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)
    invited_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="sent_invitations")

    def __str__(self):
        return f"Invitation for {self.email} as {self.get_role_display()}"
