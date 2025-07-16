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
    # Tenant-specific fields
    apartment_unit = models.ForeignKey('properties.ApartmentUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations")
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent_payment_date = models.IntegerField(null=True, blank=True, help_text="Day of month (1-28)")  # Day of month for payment
    lease_length_months = models.IntegerField(null=True, blank=True, choices=[(3, '3 months'), (6, '6 months'), (12, '12 months')])
    # Employee-specific field
    all_properties = models.BooleanField(default=False, help_text="Employee has access to all company properties")
    
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)
    invited_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="sent_invitations")

    def __str__(self):
        return f"Invitation for {self.email} as {self.get_role_display()}"
