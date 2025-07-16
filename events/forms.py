from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, time
from .models import CalendarEvent, WorkSchedule
from properties.models import Property, ApartmentUnit
from users.models import User
from maintenance.models import MaintenanceRequest

class CalendarEventForm(forms.ModelForm):
    # Custom fields for separate date and time inputs
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'})
    )
    start_hour = forms.ChoiceField(
        choices=[(i, f'{i:02d}') for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_minute = forms.ChoiceField(
        choices=[(0, '00'), (15, '15'), (30, '30'), (45, '45')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_ampm = forms.ChoiceField(
        choices=[('AM', 'AM'), ('PM', 'PM')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'})
    )
    end_hour = forms.ChoiceField(
        choices=[(i, f'{i:02d}') for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    end_minute = forms.ChoiceField(
        choices=[(0, '00'), (15, '15'), (30, '30'), (45, '45')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    end_ampm = forms.ChoiceField(
        choices=[('AM', 'AM'), ('PM', 'PM')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = CalendarEvent
        fields = [
            'title', 'description', 'event_type', 'is_all_day',
            'property', 'apartment_unit', 'location_details',
            'assigned_to', 'maintenance_request'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-textarea'}),
            'location_details': forms.TextInput(attrs={'class': 'form-input'}),
            'assigned_to': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter properties based on user's company
            if user.company:
                self.fields['property'].queryset = Property.objects.filter(company=user.company)
                
                # Filter maintenance requests based on user's company properties
                company_properties = Property.objects.filter(company=user.company)
                self.fields['maintenance_request'].queryset = MaintenanceRequest.objects.filter(
                    property__in=company_properties
                )
                
                # Filter assigned users based on company and appropriate roles
                if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
                    # Can assign to employees and landlords in the same company
                    self.fields['assigned_to'].queryset = User.objects.filter(
                        company=user.company,
                        role__in=[User.Role.LANDLORD, User.Role.EMPLOYEE]
                    )
                else:
                    # Tenants can only see landlords and employees from their property
                    self.fields['assigned_to'].queryset = User.objects.filter(
                        company=user.company,
                        role__in=[User.Role.LANDLORD, User.Role.EMPLOYEE]
                    )
            else:
                # Superuser can see all
                self.fields['property'].queryset = Property.objects.all()
                self.fields['maintenance_request'].queryset = MaintenanceRequest.objects.all()
                self.fields['assigned_to'].queryset = User.objects.filter(
                    role__in=[User.Role.LANDLORD, User.Role.EMPLOYEE]
                )

        # Update apartment unit choices based on selected property
        if 'property' in self.data:
            try:
                property_id = int(self.data.get('property'))
                self.fields['apartment_unit'].queryset = ApartmentUnit.objects.filter(property_id=property_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.property:
            self.fields['apartment_unit'].queryset = self.instance.property.units.all()
        
        # Populate datetime fields from existing instance
        if self.instance.pk:
            start_dt = self.instance.start_datetime
            end_dt = self.instance.end_datetime
            
            if start_dt:
                self.fields['start_date'].initial = start_dt.date()
                hour_12 = start_dt.hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                self.fields['start_hour'].initial = hour_12
                self.fields['start_minute'].initial = (start_dt.minute // 15) * 15  # Round to nearest 15
                self.fields['start_ampm'].initial = 'AM' if start_dt.hour < 12 else 'PM'
            
            if end_dt:
                self.fields['end_date'].initial = end_dt.date()
                hour_12 = end_dt.hour % 12
                if hour_12 == 0:
                    hour_12 = 12
                self.fields['end_hour'].initial = hour_12
                self.fields['end_minute'].initial = (end_dt.minute // 15) * 15  # Round to nearest 15
                self.fields['end_ampm'].initial = 'AM' if end_dt.hour < 12 else 'PM'

    def clean(self):
        cleaned_data = super().clean()
        
        # Get separate datetime components
        start_date = cleaned_data.get('start_date')
        start_hour = cleaned_data.get('start_hour')
        start_minute = cleaned_data.get('start_minute')
        start_ampm = cleaned_data.get('start_ampm')
        
        end_date = cleaned_data.get('end_date')
        end_hour = cleaned_data.get('end_hour')
        end_minute = cleaned_data.get('end_minute')
        end_ampm = cleaned_data.get('end_ampm')
        
        is_all_day = cleaned_data.get('is_all_day')
        
        # Convert separate components to datetime objects
        start_datetime = None
        end_datetime = None
        
        if start_date and start_hour is not None and start_minute is not None and start_ampm:
            try:
                # Convert 12-hour to 24-hour format
                hour_24 = int(start_hour)
                if start_ampm == 'PM' and hour_24 != 12:
                    hour_24 += 12
                elif start_ampm == 'AM' and hour_24 == 12:
                    hour_24 = 0
                
                start_datetime = datetime.combine(start_date, time(hour_24, int(start_minute)))
                cleaned_data['start_datetime'] = start_datetime
            except (ValueError, TypeError):
                raise ValidationError('Invalid start time.')
        
        if end_date and end_hour is not None and end_minute is not None and end_ampm:
            try:
                # Convert 12-hour to 24-hour format
                hour_24 = int(end_hour)
                if end_ampm == 'PM' and hour_24 != 12:
                    hour_24 += 12
                elif end_ampm == 'AM' and hour_24 == 12:
                    hour_24 = 0
                
                end_datetime = datetime.combine(end_date, time(hour_24, int(end_minute)))
                cleaned_data['end_datetime'] = end_datetime
            except (ValueError, TypeError):
                raise ValidationError('Invalid end time.')

        # Validate datetime range
        if start_datetime and end_datetime:
            if start_datetime >= end_datetime:
                raise ValidationError('End time must be after start time.')
            
            # For all-day events, ensure it's at least a day apart
            if is_all_day:
                time_diff = end_datetime - start_datetime
                if time_diff.days < 1:
                    raise ValidationError('All-day events must span at least one full day.')

        return cleaned_data
    
    def save(self, commit=True):
        event = super().save(commit=False)
        
        if commit:
            event.save()
            self.save_m2m()
            
            # Automatically set privacy based on assignments
            # If users are assigned, the event should be private
            if event.assigned_to.exists():
                event.is_private = True
            else:
                event.is_private = False
            event.save()
            
        return event

class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = [
            'employee', 'property', 'day_of_week',
            'start_time', 'end_time', 'effective_from',
            'effective_to', 'is_active'
        ]
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'effective_from': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'effective_to': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.company:
            # Filter properties and employees based on user's company
            self.fields['property'].queryset = Property.objects.filter(company=user.company)
            self.fields['employee'].queryset = User.objects.filter(
                company=user.company,
                role=User.Role.EMPLOYEE
            )

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        effective_from = cleaned_data.get('effective_from')
        effective_to = cleaned_data.get('effective_to')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

        if effective_from and effective_to:
            if effective_from >= effective_to:
                raise ValidationError('Effective end date must be after start date.')

        return cleaned_data

class EventFilterForm(forms.Form):
    EVENT_TYPE_CHOICES = [('', 'All Types')] + list(CalendarEvent.EventType.choices)
    PRIORITY_CHOICES = [('', 'All Priorities')] + list(CalendarEvent.Priority.choices)
    
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        required=False,
        empty_label="All Properties",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    event_type = forms.ChoiceField(
        choices=EVENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_to_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    created_by_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.company:
            self.fields['property'].queryset = Property.objects.filter(company=user.company)