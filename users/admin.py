from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    # Add custom fields to the user list display
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    
    # Add custom fields to the fieldsets in the user detail view
    # This makes them editable in the admin
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Company', {'fields': ('role', 'company')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Company', {'fields': ('role', 'company')}),
    )

admin.site.register(User, CustomUserAdmin)
