from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Message, MessageThread

User = get_user_model()

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class MessageForm(forms.ModelForm):
    attachments = MultipleFileField(
        required=False,
        help_text="You can attach multiple files"
    )
    
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Type your message here...',
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white'
            })
        }

class NewThreadForm(forms.Form):
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Message subject...',
            'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white'
        })
    )
    
    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white',
            'size': '8'
        }),
        help_text="Hold Ctrl (Cmd on Mac) to select multiple recipients"
    )
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'Type your message here...',
            'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white'
        }),
        required=False,
        help_text="Optional: You can start with a message or just create the thread"
    )
    
    attachments = MultipleFileField(
        required=False,
        help_text="You can attach multiple files"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['recipients'].queryset = self._get_available_recipients(user)
    
    def _get_available_recipients(self, user):
        """Get available recipients based on user role"""
        if user.role == User.Role.TENANT:
            # Tenants can message landlords and employees of their property
            if user.property:
                return User.objects.filter(
                    Q(role=User.Role.LANDLORD, company=user.company) |
                    Q(role=User.Role.EMPLOYEE, property=user.property)
                ).exclude(id=user.id).select_related('company', 'property')
        
        elif user.role == User.Role.EMPLOYEE:
            # Employees can message landlords from their company and tenants from their property
            recipients_query = Q()
            
            if user.company:
                recipients_query |= Q(role=User.Role.LANDLORD, company=user.company)
            
            if user.property:
                recipients_query |= Q(role=User.Role.TENANT, property=user.property)
                # Other employees from the same property
                recipients_query |= Q(role=User.Role.EMPLOYEE, property=user.property)
            
            return User.objects.filter(recipients_query).exclude(id=user.id).select_related('company', 'property')
        
        elif user.role == User.Role.LANDLORD:
            # Landlords can message all users in their company
            return User.objects.filter(
                company=user.company
            ).exclude(id=user.id).select_related('company', 'property')
        
        elif user.role == User.Role.SUPERUSER:
            # Superusers can message anyone
            return User.objects.exclude(id=user.id).select_related('company', 'property')
        
        return User.objects.none()