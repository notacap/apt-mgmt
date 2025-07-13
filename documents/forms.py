from django import forms
from django.contrib.auth import get_user_model
from .models import Document, DocumentCategory, DocumentShare
from properties.models import Property, ApartmentUnit

User = get_user_model()

class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'description', 'file', 'category', 'access_level', 'property', 'unit', 'allowed_roles', 'allowed_users']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Document title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Document description (optional)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'accept': '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png,.gif,.xlsx,.xls,.ppt,.pptx'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'access_level': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'x-model': 'accessLevel'
            }),
            'property': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'unit': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'allowed_roles': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-checkbox h-4 w-4 text-blue-600'
            }),
            'allowed_users': forms.CheckboxSelectMultiple(attrs={
                'class': 'form-checkbox h-4 w-4 text-blue-600'
            }),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Configure access level choices based on user role
        if user and user.role == 'TENANT':
            # Tenants can only create private documents - remove the field and set it in the view
            self.fields.pop('access_level', None)
            # Hide other fields for tenants
            self.fields.pop('property', None)
            self.fields.pop('unit', None)
            self.fields.pop('allowed_roles', None)
            self.fields.pop('allowed_users', None)
        else:
            # Filter properties based on user's company
            if user and user.company:
                self.fields['property'].queryset = Property.objects.filter(company=user.company)
                # Filter users for private sharing
                self.fields['allowed_users'].queryset = User.objects.filter(company=user.company).exclude(id=user.id)
            else:
                self.fields['property'].queryset = Property.objects.none()
                self.fields['allowed_users'].queryset = User.objects.none()
            
            # Initially empty unit queryset
            self.fields['unit'].queryset = ApartmentUnit.objects.none()
            
            # Role choices for allowed_roles
            role_choices = User.Role.choices
            self.fields['allowed_roles'] = forms.MultipleChoiceField(
                choices=role_choices,
                widget=forms.CheckboxSelectMultiple(attrs={
                    'class': 'form-checkbox h-4 w-4 text-blue-600'
                }),
                required=False
            )
            
            # Set property field as optional initially
            self.fields['property'].required = False
            self.fields['unit'].required = False
            self.fields['allowed_users'].required = False
            
            # If editing and property is set, filter units
            if self.instance.pk and self.instance.property:
                self.fields['unit'].queryset = ApartmentUnit.objects.filter(property=self.instance.property)

class DocumentShareForm(forms.ModelForm):
    class Meta:
        model = DocumentShare
        fields = ['shared_with', 'message']
        widgets = {
            'shared_with': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'message': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Optional message to include with the shared document'
            }),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Filter users based on company - exclude the current user
        if user and user.company:
            self.fields['shared_with'].queryset = User.objects.filter(
                company=user.company
            ).exclude(id=user.id)
        else:
            self.fields['shared_with'].queryset = User.objects.none()

class DocumentFilterForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=DocumentCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': 'px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    
    access_level = forms.ChoiceField(
        choices=[('', 'All Access Levels')] + Document.AccessLevel.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Search documents...'
        })
    )