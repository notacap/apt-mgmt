from django.contrib import admin
from .models import PaymentSchedule, RentPayment, ExpenseRecord, PaymentReceipt


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'apartment_unit', 'rent_amount', 'unit_rent_display', 'frequency', 'start_date', 'is_active']
    list_filter = ['frequency', 'is_active', 'created_at']
    search_fields = ['tenant__username', 'tenant__email', 'apartment_unit__unit_number']
    readonly_fields = ['created_at', 'updated_at', 'unit_rent_display']
    
    fieldsets = (
        ('Tenant & Unit', {
            'fields': ('tenant', 'apartment_unit', 'unit_rent_display')
        }),
        ('Payment Details', {
            'fields': ('rent_amount', 'frequency', 'payment_day'),
            'description': 'Rent amount will default to the unit rent if left blank.'
        }),
        ('Schedule Period', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def unit_rent_display(self, obj):
        """Display the current rent amount set on the apartment unit"""
        if obj.apartment_unit:
            return f"${obj.apartment_unit.rent_amount}"
        return "Select unit first"
    unit_rent_display.short_description = "Unit's Current Rent"
    unit_rent_display.admin_order_field = 'apartment_unit__rent_amount'


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_schedule', 'due_date', 'amount_due', 'amount_paid', 'status', 'payment_date']
    list_filter = ['status', 'payment_method', 'due_date', 'payment_date']
    search_fields = [
        'payment_schedule__tenant__username', 
        'payment_schedule__tenant__email',
        'reference_number'
    ]
    readonly_fields = ['created_at', 'updated_at', 'total_amount_due', 'balance_remaining', 'is_overdue']
    
    fieldsets = (
        (None, {
            'fields': ('payment_schedule', 'amount_due', 'due_date')
        }),
        ('Payment Details', {
            'fields': ('amount_paid', 'payment_date', 'payment_method', 'status', 'processed_by')
        }),
        ('Additional Information', {
            'fields': ('reference_number', 'late_fee', 'notes')
        }),
        ('Calculated Fields', {
            'fields': ('total_amount_due', 'balance_remaining', 'is_overdue'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExpenseRecord)
class ExpenseRecordAdmin(admin.ModelAdmin):
    list_display = ['property', 'apartment_unit', 'category', 'description', 'amount', 'expense_date']
    list_filter = ['category', 'expense_date', 'property']
    search_fields = ['description', 'vendor', 'receipt_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('property', 'apartment_unit', 'category', 'description', 'amount', 'expense_date')
        }),
        ('Vendor Information', {
            'fields': ('vendor', 'receipt_number')
        }),
        ('Additional Details', {
            'fields': ('notes', 'maintenance_request', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'payment', 'issued_date', 'issued_by']
    list_filter = ['issued_date']
    search_fields = ['receipt_number', 'payment__payment_schedule__tenant__username']
    readonly_fields = ['receipt_number', 'issued_date']
