from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import CalendarEvent, WorkSchedule
from properties.models import Property, ApartmentUnit
from users.models import User
from maintenance.models import MaintenanceRequest

class CalendarEventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = [
            'title', 'description', 'event_type', 'priority',
            'start_datetime', 'end_datetime', 'is_all_day',
            'property', 'apartment_unit', 'location_details',
            'assigned_to', 'maintenance_request', 'is_private'
        ]
        widgets = {
            'start_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
            'end_datetime': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
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

    def clean(self):
        cleaned_data = super().clean()
        start_datetime = cleaned_data.get('start_datetime')
        end_datetime = cleaned_data.get('end_datetime')
        is_all_day = cleaned_data.get('is_all_day')

        if start_datetime and end_datetime:
            if start_datetime >= end_datetime:
                raise ValidationError('End time must be after start time.')
            
            # For all-day events, ensure it's at least a day apart
            if is_all_day:
                time_diff = end_datetime - start_datetime
                if time_diff.days < 1:
                    raise ValidationError('All-day events must span at least one full day.')

        return cleaned_data

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
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
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