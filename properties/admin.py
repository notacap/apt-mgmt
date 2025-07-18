from django.contrib import admin
from .models import Company, Property, ApartmentUnit


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'created_at']
    list_filter = ['company', 'created_at']
    search_fields = ['name', 'address']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ApartmentUnit)
class ApartmentUnitAdmin(admin.ModelAdmin):
    list_display = ['unit_number', 'property', 'bedrooms', 'bathrooms', 'rent_amount', 'is_occupied']
    list_filter = ['property', 'bedrooms', 'bathrooms', 'is_occupied']
    search_fields = ['unit_number', 'property__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Unit Information', {
            'fields': ('property', 'unit_number', 'bedrooms', 'bathrooms')
        }),
        ('Financial', {
            'fields': ('rent_amount',),
            'description': 'Monthly rent amount for this unit. This will be used as the default for new payment schedules.'
        }),
        ('Status', {
            'fields': ('is_occupied',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
