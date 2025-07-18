from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # Add custom fields to the user list display
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'company', 'property', 'apartment_unit', 'is_staff')
    
    # Add custom fields to the fieldsets in the user detail view
    # This makes them editable in the admin
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Company', {'fields': ('role', 'company', 'property', 'apartment_unit')}),
        ('Contact Information', {'fields': ('phone_number',)}),
        ('Emergency Contact', {'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Company', {'fields': ('role', 'company', 'property', 'apartment_unit')}),
    )

admin.site.register(User, CustomUserAdmin)
