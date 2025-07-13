from django.contrib import admin
from .models import MaintenanceCategory, MaintenanceRequest, MaintenancePhoto, MaintenanceUpdate, MaintenanceInvoice


class MaintenancePhotoInline(admin.TabularInline):
    model = MaintenancePhoto
    extra = 0
    readonly_fields = ('uploaded_at',)


class MaintenanceUpdateInline(admin.TabularInline):
    model = MaintenanceUpdate
    extra = 0
    readonly_fields = ('created_at',)


class MaintenanceInvoiceInline(admin.TabularInline):
    model = MaintenanceInvoice
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(MaintenanceCategory)
class MaintenanceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_emergency', 'created_at')
    list_filter = ('is_emergency', 'created_at')
    search_fields = ('name', 'description')


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'property', 'apartment_unit', 'tenant', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority', 'category', 'property', 'created_at')
    search_fields = ('title', 'description', 'tenant__username', 'tenant__email')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    inlines = [MaintenancePhotoInline, MaintenanceUpdateInline, MaintenanceInvoiceInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'category')
        }),
        ('Location', {
            'fields': ('property', 'apartment_unit', 'location_details')
        }),
        ('Request Details', {
            'fields': ('tenant', 'status', 'priority')
        }),
        ('Assignment & Scheduling', {
            'fields': ('assigned_to', 'scheduled_date', 'estimated_completion')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MaintenancePhoto)
class MaintenancePhotoAdmin(admin.ModelAdmin):
    list_display = ('maintenance_request', 'caption', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    readonly_fields = ('uploaded_at',)


@admin.register(MaintenanceUpdate)
class MaintenanceUpdateAdmin(admin.ModelAdmin):
    list_display = ('maintenance_request', 'update_type', 'created_by', 'created_at')
    list_filter = ('update_type', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(MaintenanceInvoice)
class MaintenanceInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'vendor_name', 'amount', 'invoice_date', 'maintenance_request')
    list_filter = ('invoice_date', 'uploaded_at')
    search_fields = ('invoice_number', 'vendor_name', 'maintenance_request__title')
    readonly_fields = ('uploaded_at',)
