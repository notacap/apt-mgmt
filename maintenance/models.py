from django.db import models
from django.conf import settings
from properties.models import Property, ApartmentUnit
import uuid
import os


def maintenance_photo_upload_path(instance, filename):
    """Generate upload path for maintenance request photos"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('maintenance', 'photos', str(instance.maintenance_request.id), filename)


def maintenance_invoice_upload_path(instance, filename):
    """Generate upload path for maintenance invoices"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('maintenance', 'invoices', str(instance.id), filename)


class MaintenanceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_emergency = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Maintenance Categories"
        ordering = ['name']


class MaintenanceRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        EMERGENCY = "EMERGENCY", "Emergency"

    # Basic information
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(MaintenanceCategory, on_delete=models.CASCADE, related_name="requests")
    
    # Location
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="maintenance_requests")
    apartment_unit = models.ForeignKey(ApartmentUnit, on_delete=models.CASCADE, related_name="maintenance_requests", null=True, blank=True)
    location_details = models.CharField(max_length=200, blank=True, help_text="Specific location within unit (e.g., kitchen sink, bathroom)")
    
    # Request details
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="maintenance_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    
    # Assignment and scheduling
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_maintenance_requests")
    scheduled_date = models.DateTimeField(null=True, blank=True)
    estimated_completion = models.DateTimeField(null=True, blank=True)
    
    # Costs (tracked via invoices)
    # actual_cost removed - costs tracked via MaintenanceInvoice model
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        unit_info = f" - {self.apartment_unit}" if self.apartment_unit else ""
        return f"{self.title} ({self.property}{unit_info})"

    def save(self, *args, **kwargs):
        # Auto-set priority based on category
        if self.category and self.category.is_emergency:
            self.priority = self.Priority.EMERGENCY
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']


class MaintenancePhoto(models.Model):
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="photos")
    photo = models.ImageField(upload_to=maintenance_photo_upload_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.maintenance_request.title}"

    class Meta:
        ordering = ['uploaded_at']


class MaintenanceUpdate(models.Model):
    class UpdateType(models.TextChoices):
        STATUS_CHANGE = "STATUS_CHANGE", "Status Change"
        PROGRESS_UPDATE = "PROGRESS_UPDATE", "Progress Update"
        SCHEDULING = "SCHEDULING", "Scheduling"
        COMPLETION = "COMPLETION", "Completion"
        NOTE = "NOTE", "Note"

    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="updates")
    update_type = models.CharField(max_length=20, choices=UpdateType.choices, default=UpdateType.NOTE)
    message = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional fields for specific update types
    old_status = models.CharField(max_length=20, choices=MaintenanceRequest.Status.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=MaintenanceRequest.Status.choices, blank=True)

    def __str__(self):
        return f"{self.get_update_type_display()} for {self.maintenance_request.title}"

    class Meta:
        ordering = ['-created_at']


class MaintenanceInvoice(models.Model):
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, related_name="invoices")
    vendor_name = models.CharField(max_length=200)
    invoice_number = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_date = models.DateField()
    invoice_file = models.FileField(upload_to=maintenance_invoice_upload_path, null=True, blank=True)
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Link to document record for proper access control
    document = models.ForeignKey('documents.Document', on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_invoices')

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.vendor_name}"

    class Meta:
        ordering = ['-invoice_date']
