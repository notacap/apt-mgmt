from django import forms
from django.db import transaction
from .models import User, Invitation
from properties.models import Company, Property, ApartmentUnit
from django.contrib.auth.models import Group

class LandlordCreationForm(forms.ModelForm):
    company_name = forms.CharField(max_length=255, required=True, help_text="The name of the management company.")

    class Meta:
        model = User
        fields = ["username", "email", "password", "company_name"]

    @transaction.atomic
    def save(self, commit=True):
        company_name = self.cleaned_data.pop("company_name")
        company, created = Company.objects.get_or_create(name=company_name)
        
        user = super().save(commit=False)
        user.role = User.Role.LANDLORD
        user.company = company
        user.set_password(self.cleaned_data["password"])
        
        if commit:
            user.save()
            landlord_group = Group.objects.get(name='Landlords')
            user.groups.add(landlord_group)
        return user 

class InvitationForm(forms.ModelForm):
    property = forms.ModelChoiceField(queryset=Property.objects.none(), required=True)
    apartment_unit = forms.ModelChoiceField(
        queryset=ApartmentUnit.objects.none(), 
        required=False,
        help_text="Select unit for tenant invitations"
    )
    
    class Meta:
        model = Invitation
        fields = ["email", "role", "property", "apartment_unit", "lease_length_months", 
                 "rent_payment_date", "lease_start_date", "all_properties"]
        labels = {
            'apartment_unit': 'Apartment Unit',
            'lease_length_months': 'Lease Length',
            'rent_payment_date': 'Payment Day',
            'lease_start_date': 'Lease Start Date',
            'all_properties': 'Grant access to all properties'
        }
        widgets = {
            'lease_start_date': forms.DateInput(attrs={'type': 'date'}),
            'rent_payment_date': forms.NumberInput(attrs={'min': '1', 'max': '28', 'placeholder': 'Day of month (1-28)'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(InvitationForm, self).__init__(*args, **kwargs)
        if user:
            # Set property queryset based on user's company
            self.fields['property'].queryset = Property.objects.filter(company=user.company)
            
            # Set apartment unit queryset to include all units in user's company
            # This allows the form validation to pass
            self.fields['apartment_unit'].queryset = ApartmentUnit.objects.filter(
                property__company=user.company,
                is_occupied=False
            )
            
            # Limit role choices - remove SUPERUSER and LANDLORD
            role_choices = [(choice[0], choice[1]) for choice in User.Role.choices 
                           if choice[0] not in ['SUPERUSER', 'LANDLORD']]
            self.fields['role'].choices = role_choices
            
            # Add CSS classes for styling
            self.fields['all_properties'].widget.attrs['class'] = 'mr-2'
            
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        property_obj = cleaned_data.get('property')
        
        if role == 'TENANT':
            # Validate tenant-specific fields
            apartment_unit = cleaned_data.get('apartment_unit')
            if not apartment_unit:
                raise forms.ValidationError("Apartment unit is required for tenant invitations.")
            if not cleaned_data.get('lease_length_months'):
                raise forms.ValidationError("Lease length is required for tenant invitations.")
            if not cleaned_data.get('rent_payment_date'):
                raise forms.ValidationError("Payment day is required for tenant invitations.")
            if not cleaned_data.get('lease_start_date'):
                raise forms.ValidationError("Lease start date is required for tenant invitations.")
            
            # Validate that apartment unit belongs to selected property
            if property_obj and apartment_unit:
                if apartment_unit.property != property_obj:
                    raise forms.ValidationError("Selected apartment unit does not belong to the selected property.")
                if apartment_unit.is_occupied:
                    raise forms.ValidationError("Selected apartment unit is already occupied.")
            
            # Clear employee-specific fields
            cleaned_data['all_properties'] = False
        elif role == 'EMPLOYEE':
            # Clear tenant-specific fields
            cleaned_data['apartment_unit'] = None
            cleaned_data['lease_length_months'] = None
            cleaned_data['rent_payment_date'] = None
            cleaned_data['lease_start_date'] = None
            # If all_properties is True, property can be None
            if cleaned_data.get('all_properties') and not property_obj:
                cleaned_data['property'] = None
        
        return cleaned_data

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'Email Address'
            }),
        }
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email Address',
        }

class EmployeeManagementForm(forms.ModelForm):
    """Form for landlords to edit employee details and property assignments"""
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(), 
        required=False,
        help_text="Assign employee to a specific property (leave blank for company-wide access)",
        label="Property Assignment"
    )
    
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_number", "property"]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'Last Name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': 'Email Address'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors',
                'placeholder': '(555) 123-4567'
            }),
        }
        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email Address',
            'phone_number': 'Phone Number',
        }
        
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # The current user (landlord)
        super(EmployeeManagementForm, self).__init__(*args, **kwargs)
        
        if user and user.company:
            # Set property queryset based on landlord's company
            self.fields['property'].queryset = Property.objects.filter(company=user.company)
            
            # Add CSS classes to the property field
            self.fields['property'].widget.attrs.update({
                'class': 'w-full px-3 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white transition-colors'
            })
            
            # Set initial property value if the employee being edited has one
            if self.instance and hasattr(self.instance, 'property'):
                self.fields['property'].initial = self.instance.property

class InvitationAcceptanceForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(),
        help_text="Create a secure password for your account"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(),
        help_text="Re-enter your password to confirm"
    )
    
    class Meta:
        model = User
        fields = [
            "username", "password", "first_name", "last_name", 
            "phone_number", "emergency_contact_name", 
            "emergency_contact_phone", "emergency_contact_relationship"
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={'placeholder': '(555) 123-4567'}),
            'emergency_contact_phone': forms.TextInput(attrs={'placeholder': '(555) 123-4567'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'placeholder': 'e.g., Spouse, Parent, Sibling, Friend'}),
        }
        labels = {
            'phone_number': 'Phone Number',
            'emergency_contact_name': 'Emergency Contact Name',
            'emergency_contact_phone': 'Emergency Contact Phone',
            'emergency_contact_relationship': 'Relationship to Emergency Contact',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'phone_number', 
                          'emergency_contact_name', 'emergency_contact_phone', 
                          'emergency_contact_relationship']
        
        for field_name in required_fields:
            if not cleaned_data.get(field_name):
                self.add_error(field_name, "This field is required.")
        
        return cleaned_data 