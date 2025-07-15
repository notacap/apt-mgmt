from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from maintenance.models import MaintenanceRequest
from .models import CalendarEvent

@receiver(post_save, sender=MaintenanceRequest)
def create_maintenance_calendar_event(sender, instance, created, **kwargs):
    """
    Create a calendar event when a maintenance request is scheduled
    """
    # Only create calendar event if the request has a scheduled date
    if instance.scheduled_date and instance.assigned_to:
        # Check if calendar event already exists for this maintenance request
        existing_event = CalendarEvent.objects.filter(maintenance_request=instance).first()
        
        if existing_event:
            # Update existing event
            existing_event.title = f"Maintenance: {instance.title}"
            existing_event.description = f"Maintenance work for: {instance.description}\n\nLocation: {instance.location_details or 'See maintenance request for details'}"
            existing_event.start_datetime = instance.scheduled_date
            # Default to 2 hours for maintenance duration
            existing_event.end_datetime = instance.estimated_completion or (instance.scheduled_date + timedelta(hours=2))
            existing_event.property = instance.property
            existing_event.apartment_unit = instance.apartment_unit
            existing_event.location_details = instance.location_details
            existing_event.priority = get_calendar_priority_from_maintenance(instance.priority)
            existing_event.save()
            
            # Update assigned users
            existing_event.assigned_to.clear()
            existing_event.assigned_to.add(instance.assigned_to)
        else:
            # Create new calendar event
            calendar_event = CalendarEvent.objects.create(
                title=f"Maintenance: {instance.title}",
                description=f"Maintenance work for: {instance.description}\n\nLocation: {instance.location_details or 'See maintenance request for details'}",
                event_type=CalendarEvent.EventType.MAINTENANCE,
                priority=get_calendar_priority_from_maintenance(instance.priority),
                start_datetime=instance.scheduled_date,
                end_datetime=instance.estimated_completion or (instance.scheduled_date + timedelta(hours=2)),
                property=instance.property,
                apartment_unit=instance.apartment_unit,
                location_details=instance.location_details,
                created_by=instance.assigned_to,
                maintenance_request=instance
            )
            
            # Assign to the maintenance worker
            calendar_event.assigned_to.add(instance.assigned_to)

def get_calendar_priority_from_maintenance(maintenance_priority):
    """Convert maintenance priority to calendar priority"""
    priority_mapping = {
        'EMERGENCY': CalendarEvent.Priority.URGENT,
        'HIGH': CalendarEvent.Priority.HIGH,
        'MEDIUM': CalendarEvent.Priority.MEDIUM,
        'LOW': CalendarEvent.Priority.LOW,
    }
    return priority_mapping.get(maintenance_priority, CalendarEvent.Priority.MEDIUM)