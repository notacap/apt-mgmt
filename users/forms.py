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
        fields = ["email", "role", "property", "apartment_unit", "rent_amount", 
                 "rent_payment_date", "lease_length_months", "all_properties"]
        widgets = {
            'rent_payment_date': forms.NumberInput(attrs={'min': 1, 'max': 28}),
            'rent_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(InvitationForm, self).__init__(*args, **kwargs)
        if user:
            # Set property queryset based on user's company
            self.fields['property'].queryset = Property.objects.filter(company=user.company)
            
            # Limit role choices - remove SUPERUSER and LANDLORD
            role_choices = [(choice[0], choice[1]) for choice in User.Role.choices 
                           if choice[0] not in ['SUPERUSER', 'LANDLORD']]
            self.fields['role'].choices = role_choices
            
            # Initially hide tenant/employee specific fields
            self.fields['apartment_unit'].widget.attrs['style'] = 'display:none;'
            self.fields['rent_amount'].widget.attrs['style'] = 'display:none;'
            self.fields['rent_payment_date'].widget.attrs['style'] = 'display:none;'
            self.fields['lease_length_months'].widget.attrs['style'] = 'display:none;'
            self.fields['all_properties'].widget.attrs['style'] = 'display:none;'
            
    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        property_obj = cleaned_data.get('property')
        
        if role == 'TENANT':
            # Validate tenant-specific fields
            if not cleaned_data.get('apartment_unit'):
                raise forms.ValidationError("Apartment unit is required for tenant invitations.")
            if not cleaned_data.get('rent_amount'):
                raise forms.ValidationError("Rent amount is required for tenant invitations.")
            if not cleaned_data.get('rent_payment_date'):
                raise forms.ValidationError("Rent payment date is required for tenant invitations.")
            if not cleaned_data.get('lease_length_months'):
                raise forms.ValidationError("Lease length is required for tenant invitations.")
            # Clear employee-specific fields
            cleaned_data['all_properties'] = False
        elif role == 'EMPLOYEE':
            # Clear tenant-specific fields
            cleaned_data['apartment_unit'] = None
            cleaned_data['rent_amount'] = None
            cleaned_data['rent_payment_date'] = None
            cleaned_data['lease_length_months'] = None
            # If all_properties is True, property can be None
            if cleaned_data.get('all_properties') and not property_obj:
                cleaned_data['property'] = None
        
        return cleaned_data

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

class InvitationAcceptanceForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "password"] 