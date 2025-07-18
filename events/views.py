from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import json

from .models import CalendarEvent, WorkSchedule
from .forms import CalendarEventForm, WorkScheduleForm, EventFilterForm
from properties.models import Property
from users.models import User
from communication.models import Notification

@login_required
def calendar_view(request):
    """Main calendar view - defaults to month view"""
    return calendar_month_view(request)

@login_required
def calendar_month_view(request):
    """Month view of the calendar"""
    # Get current date or date from parameters
    today = timezone.localtime().date()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Calculate month boundaries
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    # Get events for the month
    events = get_user_events(request.user, start_date, end_date)
    
    # Apply filters
    filter_form = EventFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        events = apply_event_filters(events, filter_form.cleaned_data, request.user)
    
    context = {
        'events': events,
        'filter_form': filter_form,
        'current_date': start_date,
        'current_month_year': start_date,  # For display purposes
        'today': today,
        'view_type': 'month',
    }
    
    return render(request, 'events/calendar_month.html', context)

@login_required
def calendar_week_view(request):
    """Week view of the calendar"""
    today = timezone.localtime().date()
    
    # Get the start of the week (Monday)
    days_since_monday = today.weekday()
    start_date = today - timedelta(days=days_since_monday)
    end_date = start_date + timedelta(days=6)
    
    # Allow navigation with date parameter
    if 'date' in request.GET:
        try:
            date_param = datetime.strptime(request.GET['date'], '%Y-%m-%d').date()
            days_since_monday = date_param.weekday()
            start_date = date_param - timedelta(days=days_since_monday)
            end_date = start_date + timedelta(days=6)
        except ValueError:
            pass
    
    # Get events for the week
    events = get_user_events(request.user, start_date, end_date)
    
    # Apply filters
    filter_form = EventFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        events = apply_event_filters(events, filter_form.cleaned_data, request.user)
    
    # Generate week days
    week_days = []
    current_date = start_date
    for i in range(7):
        # Filter events that span through this day (start <= current_date <= end)
        day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(current_date, datetime.max.time()))
        
        day_events = events.filter(
            start_datetime__lte=day_end,
            end_datetime__gte=day_start
        ).order_by('start_datetime')
        
        week_days.append({
            'date': current_date,
            'events': day_events,
            'is_today': current_date == today
        })
        current_date += timedelta(days=1)
    
    context = {
        'week_days': week_days,
        'start_date': start_date,
        'end_date': end_date,
        'filter_form': filter_form,
        'view_type': 'week',
        'today': today,
    }
    
    return render(request, 'events/calendar_week.html', context)

@login_required
def calendar_day_view(request):
    """Day view of the calendar"""
    today = timezone.localtime().date()
    
    # Get date from parameter or use today
    view_date = today
    if 'date' in request.GET:
        try:
            view_date = datetime.strptime(request.GET['date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Get events for the day
    events = get_user_events(request.user, view_date, view_date)
    
    # Apply filters
    filter_form = EventFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        events = apply_event_filters(events, filter_form.cleaned_data, request.user)
    
    # Order by start time
    events = events.order_by('start_datetime')
    
    context = {
        'events': events,
        'view_date': view_date,
        'filter_form': filter_form,
        'view_type': 'day',
        'today': today,
    }
    
    return render(request, 'events/calendar_day.html', context)

def get_user_events(user, start_date, end_date):
    """Get events visible to the user within the date range"""
    # Convert dates to datetime for filtering
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
    
    # Base query
    events = CalendarEvent.objects.filter(
        start_datetime__lte=end_datetime,
        end_datetime__gte=start_datetime
    )
    
    # Filter based on user role and access
    if user.role == User.Role.SUPERUSER:
        # Superuser can see all events
        pass
    elif user.role == User.Role.LANDLORD:
        # Landlords see all events in their company
        events = events.filter(
            Q(property__company=user.company) |
            Q(created_by=user) |
            Q(assigned_to=user)
        )
    elif user.role == User.Role.EMPLOYEE:
        # Employees see events based on their property access
        if user.property is None:
            # Employee has access to all properties in their company
            events = events.filter(
                Q(property__company=user.company) |
                Q(created_by=user) |
                Q(assigned_to=user)
            )
        else:
            # Employee has access only to their assigned property
            events = events.filter(
                Q(property=user.property) |
                Q(created_by=user) |
                Q(assigned_to=user)
            )
    else:  # Tenant
        # Tenants see:
        # 1. Non-maintenance events in their property that are not private
        # 2. Events they created
        # 3. Events they are assigned to
        # 4. Maintenance events ONLY for their own maintenance requests
        events = events.filter(
            Q(property=user.property, is_private=False, maintenance_request__isnull=True) |  # Non-maintenance events in property
            Q(created_by=user) |
            Q(assigned_to=user) |
            Q(maintenance_request__tenant=user)  # Only their own maintenance events
        )
    
    return events.distinct()

def apply_event_filters(events, filters, user):
    """Apply additional filters to events queryset"""
    if filters.get('property'):
        events = events.filter(property=filters['property'])
    
    if filters.get('event_type'):
        events = events.filter(event_type=filters['event_type'])
    
    if filters.get('assigned_to_me'):
        events = events.filter(assigned_to=user)
    
    if filters.get('created_by_me'):
        events = events.filter(created_by=user)
    
    return events

@login_required
def create_event(request):
    """Create a new calendar event"""
    # Prevent tenants from creating events
    if request.user.role == User.Role.TENANT:
        return HttpResponseForbidden("Tenants are not allowed to create events.")
    
    if request.method == 'POST':
        form = CalendarEventForm(request.POST, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            
            # Validate user can create events for this property
            if not can_user_manage_property(request.user, event.property):
                return HttpResponseForbidden("You don't have permission to create events for this property.")
            
            # Use form's save method to handle automatic privacy setting
            event = form.save()
            
            # Create notifications for assigned users
            for assigned_user in event.assigned_to.all():
                if assigned_user != request.user:
                    Notification.objects.create(
                        user=assigned_user,
                        notification_type=Notification.NotificationType.GENERAL,
                        title=f"New Event: {event.title}",
                        message=f"You have been assigned to a new event: {event.title} on {event.start_datetime.strftime('%Y-%m-%d %H:%M')}",
                        related_object_id=event.id,
                        related_object_type='calendar_event'
                    )
            
            messages.success(request, 'Event created successfully.')
            return redirect('events:calendar')
    else:
        form = CalendarEventForm(user=request.user)
    
    return render(request, 'events/create_event.html', {'form': form})

@login_required
def event_detail(request, event_id):
    """View event details"""
    event = get_object_or_404(CalendarEvent, id=event_id)
    
    # Check user permissions
    if not can_user_view_event(request.user, event):
        return HttpResponseForbidden("You don't have permission to view this event.")
    
    can_edit = can_user_edit_event(request.user, event)
    
    return render(request, 'events/event_detail.html', {
        'event': event,
        'can_edit': can_edit
    })

@login_required
def edit_event(request, event_id):
    """Edit an existing event"""
    event = get_object_or_404(CalendarEvent, id=event_id)
    
    # Check user permissions
    if not can_user_edit_event(request.user, event):
        return HttpResponseForbidden("You don't have permission to edit this event.")
    
    if request.method == 'POST':
        form = CalendarEventForm(request.POST, instance=event, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('events:event_detail', event_id=event.id)
    else:
        form = CalendarEventForm(instance=event, user=request.user)
    
    return render(request, 'events/edit_event.html', {
        'form': form,
        'event': event
    })

@login_required
def delete_event(request, event_id):
    """Delete an event"""
    event = get_object_or_404(CalendarEvent, id=event_id)
    
    # Check user permissions
    if not can_user_edit_event(request.user, event):
        return HttpResponseForbidden("You don't have permission to delete this event.")
    
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted successfully.')
        return redirect('events:calendar')
    
    return render(request, 'events/delete_event.html', {'event': event})

@login_required
def work_schedule_list(request):
    """List work schedules"""
    if request.user.role not in [User.Role.SUPERUSER, User.Role.LANDLORD, User.Role.EMPLOYEE]:
        return HttpResponseForbidden("You don't have permission to view work schedules.")
    
    # Filter schedules based on user role
    if request.user.role == User.Role.SUPERUSER:
        schedules = WorkSchedule.objects.all()
    elif request.user.role == User.Role.LANDLORD:
        schedules = WorkSchedule.objects.filter(property__company=request.user.company)
    else:  # Employee
        schedules = WorkSchedule.objects.filter(employee=request.user)
    
    return render(request, 'events/work_schedule_list.html', {
        'schedules': schedules
    })

@login_required
def create_work_schedule(request):
    """Create a new work schedule"""
    if request.user.role not in [User.Role.SUPERUSER, User.Role.LANDLORD]:
        return HttpResponseForbidden("You don't have permission to create work schedules.")
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Work schedule created successfully.')
            return redirect('events:work_schedule_list')
    else:
        form = WorkScheduleForm(user=request.user)
    
    return render(request, 'events/create_work_schedule.html', {'form': form})

@login_required
def edit_work_schedule(request, schedule_id):
    """Edit a work schedule"""
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    # Check permissions
    if not can_user_manage_work_schedule(request.user, schedule):
        return HttpResponseForbidden("You don't have permission to edit this work schedule.")
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=schedule, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Work schedule updated successfully.')
            return redirect('events:work_schedule_list')
    else:
        form = WorkScheduleForm(instance=schedule, user=request.user)
    
    return render(request, 'events/edit_work_schedule.html', {
        'form': form,
        'schedule': schedule
    })

@login_required
def delete_work_schedule(request, schedule_id):
    """Delete a work schedule"""
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    # Check permissions
    if not can_user_manage_work_schedule(request.user, schedule):
        return HttpResponseForbidden("You don't have permission to delete this work schedule.")
    
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, 'Work schedule deleted successfully.')
        return redirect('events:work_schedule_list')
    
    return render(request, 'events/delete_work_schedule.html', {'schedule': schedule})

@login_required
def get_events_json(request):
    """AJAX endpoint to get events as JSON for calendar widgets"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    if not start_date or not end_date:
        return JsonResponse({'error': 'Start and end dates required'}, status=400)
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get base events for user
    events = get_user_events(request.user, start_date, end_date)
    
    # Apply filters like other calendar views
    filter_form = EventFilterForm(request.GET, user=request.user)
    if filter_form.is_valid():
        events = apply_event_filters(events, filter_form.cleaned_data, request.user)
    
    events_data = []
    for event in events:
        # For all-day events, use date strings to avoid timezone issues
        if event.is_all_day:
            # Convert to local timezone first, then get the date
            local_start = timezone.localtime(event.start_datetime)
            local_end = timezone.localtime(event.end_datetime)
            
            # For single-day all-day events, use the start date for both start and end
            start_date = local_start.date()
            
            # If start and end are on the same local date, it's a single-day event
            if local_start.date() == local_end.date():
                end_date = start_date
            else:
                end_date = local_end.date()
            
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()
        else:
            # Convert to local timezone first to ensure proper date comparison
            local_start = timezone.localtime(event.start_datetime)
            local_end = timezone.localtime(event.end_datetime)
            
            # If the event starts and ends on the same local date, ensure JavaScript treats it as same-day
            if local_start.date() == local_end.date():
                # For same-day events, we can use the full datetime but need to ensure
                # JavaScript will recognize them as same-day by using the local time
                start_str = local_start.isoformat()
                end_str = local_end.isoformat()
            else:
                # For truly multi-day events, use the original datetime
                start_str = event.start_datetime.isoformat()
                end_str = event.end_datetime.isoformat()
            
        events_data.append({
            'id': event.id,
            'title': event.title,
            'start': start_str,
            'end': end_str,
            'allDay': event.is_all_day,
            'backgroundColor': get_event_color(event.event_type),
            'borderColor': get_event_color(event.event_type),
            'url': f'/calendar/event/{event.id}/',
        })
    
    return JsonResponse(events_data, safe=False)

# Helper functions
def can_user_view_event(user, event):
    """Check if user can view the event"""
    if user.role == User.Role.SUPERUSER:
        return True
    
    if event.created_by == user or user in event.assigned_to.all():
        return True
    
    if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        return event.property.company == user.company
    
    # Tenants can view non-private events in their property
    return event.property == user.property and not event.is_private

def can_user_edit_event(user, event):
    """Check if user can edit the event"""
    if user.role == User.Role.SUPERUSER:
        return True
    
    if event.created_by == user:
        return True
    
    if user.role == User.Role.LANDLORD and event.property.company == user.company:
        return True
    
    return False

def can_user_manage_property(user, property):
    """Check if user can manage events for a property"""
    if user.role == User.Role.SUPERUSER:
        return True
    
    if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        return property.company == user.company
    
    return property == user.property

def can_user_manage_work_schedule(user, schedule):
    """Check if user can manage a work schedule"""
    if user.role == User.Role.SUPERUSER:
        return True
    
    if user.role == User.Role.LANDLORD:
        return schedule.property.company == user.company
    
    return False

def get_event_color(event_type):
    """Get color for event type"""
    colors = {
        'MAINTENANCE': '#f59e0b',  # amber
        'MEETING': '#3b82f6',      # blue
        'INSPECTION': '#8b5cf6',   # purple
        'WORK_SCHEDULE': '#10b981', # emerald
        'LEASE_SIGNING': '#ef4444', # red
        'PROPERTY_SHOWING': '#06b6d4', # cyan
        'GENERAL': '#6b7280',      # gray
    }
    return colors.get(event_type, '#6b7280')
