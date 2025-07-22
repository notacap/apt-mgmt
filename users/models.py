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
    apartment_unit = models.ForeignKey('properties.ApartmentUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name="tenant")
    
    # Multi-property assignments for employees
    assigned_properties = models.ManyToManyField(
        Property, 
        related_name="assigned_employees", 
        blank=True,
        help_text="Properties this employee has access to (for employees only)"
    )
    
    # For employees: if assigned_properties is empty, they have company-wide access
    # The old 'property' field will be kept for backward compatibility and tenant assignments
    
    # Contact information
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Emergency contact information
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, null=True)
    
    def has_property_access(self, property):
        """Check if user has access to a specific property"""
        if self.role == self.Role.SUPERUSER:
            return True
        if self.role == self.Role.LANDLORD and self.company == property.company:
            return True
        if self.role == self.Role.EMPLOYEE:
            # Check if employee has company-wide access (no assigned properties)
            if not self.assigned_properties.exists() and self.company == property.company:
                return True  # Company-wide access
            # Check if employee is specifically assigned to this property
            elif self.assigned_properties.filter(id=property.id).exists():
                return True  # Specific property access
            # Backward compatibility: check old single property field
            elif self.property == property:
                return True  # Legacy single property access
        if self.role == self.Role.TENANT and self.property == property:
            return True
        return False
    
    def get_accessible_properties(self):
        """Get all properties this user has access to"""
        if self.role == self.Role.SUPERUSER:
            from properties.models import Property
            return Property.objects.all()
        elif self.role == self.Role.LANDLORD and self.company:
            return self.company.properties.all()
        elif self.role == self.Role.EMPLOYEE:
            if not self.assigned_properties.exists() and self.company:
                # Company-wide access
                return self.company.properties.all()
            else:
                # Specific properties access
                accessible = self.assigned_properties.all()
                # Include legacy single property if set
                if self.property:
                    accessible = accessible.union(Property.objects.filter(id=self.property.id))
                return accessible
        elif self.role == self.Role.TENANT and self.property:
            from properties.models import Property
            return Property.objects.filter(id=self.property.id)
        else:
            from properties.models import Property
            return Property.objects.none()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Invitation(models.Model):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=50, choices=User.Role.choices)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="invitations", null=True, blank=True)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="invitations", null=True, blank=True)
    
    # Multi-property assignments for employee invitations
    assigned_properties = models.ManyToManyField(
        Property,
        related_name="employee_invitations",
        blank=True,
        help_text="Properties this employee will have access to"
    )
    
    # Tenant-specific fields
    apartment_unit = models.ForeignKey('properties.ApartmentUnit', on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations")
    rent_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rent_payment_date = models.IntegerField(null=True, blank=True, help_text="Day of month (1-28)")  # Day of month for payment
    lease_start_date = models.DateField(null=True, blank=True, help_text="Date when the tenant's lease begins")
    lease_length_months = models.IntegerField(null=True, blank=True, choices=[(3, '3 months'), (6, '6 months'), (12, '12 months')])
    # Employee-specific field (kept for backward compatibility)
    all_properties = models.BooleanField(default=False, help_text="Employee has access to all company properties")
    
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_accepted = models.BooleanField(default=False)
    invited_by = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="sent_invitations")

    def __str__(self):
        return f"Invitation for {self.email} as {self.get_role_display()}"
