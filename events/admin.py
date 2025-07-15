from django.contrib import admin
from .models import CalendarEvent, WorkSchedule

@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'priority', 'start_datetime', 'end_datetime', 'property', 'created_by']
    list_filter = ['event_type', 'priority', 'property', 'is_completed', 'is_cancelled']
    search_fields = ['title', 'description', 'location_details']
    filter_horizontal = ['assigned_to']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'event_type', 'priority')
        }),
        ('Date and Time', {
            'fields': ('start_datetime', 'end_datetime', 'is_all_day')
        }),
        ('Location', {
            'fields': ('property', 'apartment_unit', 'location_details')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Integration', {
            'fields': ('maintenance_request',)
        }),
        ('Status', {
            'fields': ('is_completed', 'is_cancelled', 'is_private')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'property', 'day_of_week', 'start_time', 'end_time', 'effective_from', 'effective_to', 'is_active']
    list_filter = ['day_of_week', 'property', 'is_active']
    search_fields = ['employee__username', 'employee__first_name', 'employee__last_name']
    readonly_fields = ['created_at', 'updated_at']
