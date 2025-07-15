from django.db import models
from django.conf import settings
from properties.models import Property, ApartmentUnit
from maintenance.models import MaintenanceRequest

class CalendarEvent(models.Model):
    class EventType(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        MEETING = "MEETING", "Meeting"
        INSPECTION = "INSPECTION", "Inspection"
        WORK_SCHEDULE = "WORK_SCHEDULE", "Work Schedule"
        LEASE_SIGNING = "LEASE_SIGNING", "Lease Signing"
        PROPERTY_SHOWING = "PROPERTY_SHOWING", "Property Showing"
        GENERAL = "GENERAL", "General"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    # Basic event information
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.GENERAL)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)

    # Date and time
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    is_all_day = models.BooleanField(default=False)

    # Location and associations
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="events")
    apartment_unit = models.ForeignKey(ApartmentUnit, on_delete=models.CASCADE, related_name="events", null=True, blank=True)
    location_details = models.CharField(max_length=200, blank=True)

    # User associations
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_events")
    assigned_to = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assigned_events")

    # Integration with maintenance requests
    maintenance_request = models.ForeignKey(MaintenanceRequest, on_delete=models.CASCADE, null=True, blank=True, related_name="calendar_events")

    # Status and visibility
    is_completed = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)  # Private to creator only

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['start_datetime']

class WorkSchedule(models.Model):
    """Recurring work schedule for employees"""
    class DayOfWeek(models.TextChoices):
        MONDAY = "MONDAY", "Monday"
        TUESDAY = "TUESDAY", "Tuesday"
        WEDNESDAY = "WEDNESDAY", "Wednesday"
        THURSDAY = "THURSDAY", "Thursday"
        FRIDAY = "FRIDAY", "Friday"
        SATURDAY = "SATURDAY", "Saturday"
        SUNDAY = "SUNDAY", "Sunday"

    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_schedules")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="work_schedules")
    day_of_week = models.CharField(max_length=10, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    # Date range for the schedule
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)  # None means indefinite

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = ('employee', 'property', 'day_of_week', 'effective_from')
