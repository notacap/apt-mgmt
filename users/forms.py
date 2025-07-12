from django import forms
from django.db import transaction
from .models import User, Invitation
from properties.models import Company, Property
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

    class Meta:
        model = Invitation
        fields = ["email", "role", "property"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(InvitationForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['property'].queryset = Property.objects.filter(company=user.company)

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

class InvitationAcceptanceForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "password"] 