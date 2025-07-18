from django import forms
from django.contrib.auth import get_user_model
from .models import PaymentSchedule, RentPayment, ExpenseRecord, PaymentReceipt

User = get_user_model()


class PaymentScheduleForm(forms.ModelForm):
    class Meta:
        model = PaymentSchedule
        fields = ['tenant', 'apartment_unit', 'rent_amount', 'frequency', 'payment_day', 'start_date', 'end_date', 'is_active']
        labels = {
            'payment_day': 'Payment Day',
            'start_date': 'Lease Start Date',
            'end_date': 'Lease End Date',
            'rent_amount': 'Rent Amount',
            'is_active': 'Active Schedule'
        }
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'rent_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'payment_day': forms.NumberInput(attrs={'min': '1', 'max': '28'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter tenants to only those in the user's company/property
            if user.role in ['LANDLORD', 'EMPLOYEE']:
                tenants = User.objects.filter(
                    role='TENANT',
                    company=user.company
                )
                if user.property:
                    tenants = tenants.filter(property=user.property)
                self.fields['tenant'].queryset = tenants
                
                # Filter apartment units to the user's company/property
                from properties.models import ApartmentUnit
                units = ApartmentUnit.objects.filter(property__company=user.company)
                if user.property:
                    units = units.filter(property=user.property)
                self.fields['apartment_unit'].queryset = units


class RentPaymentForm(forms.ModelForm):
    class Meta:
        model = RentPayment
        fields = ['amount_paid', 'payment_date', 'payment_method', 'reference_number', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ExpenseRecordForm(forms.ModelForm):
    class Meta:
        model = ExpenseRecord
        fields = ['property', 'apartment_unit', 'category', 'description', 'amount', 
                 'expense_date', 'vendor', 'receipt_number', 'notes', 'maintenance_request']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role in ['LANDLORD', 'EMPLOYEE']:
            # Filter properties to user's company
            from properties.models import Property, ApartmentUnit
            properties = Property.objects.filter(company=user.company)
            if user.property:
                properties = properties.filter(id=user.property.id)
            self.fields['property'].queryset = properties
            
            # Initially set apartment_unit to none, will be filtered via HTMX
            self.fields['apartment_unit'].queryset = ApartmentUnit.objects.none()
            self.fields['apartment_unit'].required = False
            
            # Filter maintenance requests to user's company
            from maintenance.models import MaintenanceRequest
            maintenance_requests = MaintenanceRequest.objects.filter(
                apartment_unit__property__company=user.company
            )
            if user.property:
                maintenance_requests = maintenance_requests.filter(
                    apartment_unit__property=user.property
                )
            self.fields['maintenance_request'].queryset = maintenance_requests
            self.fields['maintenance_request'].required = False


class TenantPaymentForm(forms.Form):
    """Simplified form for tenants to record their own payments"""
    amount_paid = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    payment_method = forms.ChoiceField(
        choices=RentPayment.PaymentMethod.choices
    )
    reference_number = forms.CharField(
        max_length=100, 
        required=False,
        help_text="Check number, transaction ID, etc."
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )


class PaymentFilterForm(forms.Form):
    """Form for filtering payments in list views"""
    STATUS_CHOICES = [('', 'All Statuses')] + list(RentPayment.Status.choices)
    PAYMENT_METHOD_CHOICES = [('', 'All Methods')] + list(RentPayment.PaymentMethod.choices)
    
    status = forms.ChoiceField(choices=STATUS_CHOICES, required=False)
    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES, required=False)
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search tenant, unit, reference...'})
    )


class ExpenseFilterForm(forms.Form):
    """Form for filtering expenses in list views"""
    CATEGORY_CHOICES = [('', 'All Categories')] + list(ExpenseRecord.Category.choices)
    
    category = forms.ChoiceField(choices=CATEGORY_CHOICES, required=False)
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search description, vendor...'})
    )