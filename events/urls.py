from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    # Calendar views
    path('', views.calendar_view, name='calendar'),
    path('month/', views.calendar_month_view, name='calendar_month'),
    path('week/', views.calendar_week_view, name='calendar_week'),
    path('day/', views.calendar_day_view, name='calendar_day'),
    
    # Event management
    path('event/create/', views.create_event, name='create_event'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/delete/', views.delete_event, name='delete_event'),
    
    # Work schedule management
    path('schedule/', views.work_schedule_list, name='work_schedule_list'),
    path('schedule/create/', views.create_work_schedule, name='create_work_schedule'),
    path('schedule/<int:schedule_id>/edit/', views.edit_work_schedule, name='edit_work_schedule'),
    path('schedule/<int:schedule_id>/delete/', views.delete_work_schedule, name='delete_work_schedule'),
    
    # AJAX endpoints for calendar data
    path('api/events/', views.get_events_json, name='get_events_json'),
]