from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class PaymentSchedule(models.Model):
    """Defines recurring payment schedule for a tenant in a specific unit"""
    
    class Frequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"
        ANNUALLY = "ANNUALLY", "Annually"
    
    tenant = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name="payment_schedules",
        limit_choices_to={'role': 'TENANT'}
    )
    apartment_unit = models.ForeignKey(
        "properties.ApartmentUnit",
        on_delete=models.CASCADE,
        related_name="payment_schedules"
    )
    rent_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.MONTHLY
    )
    payment_day = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Day of month when payment is due (1-28)"
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def current_unit_rent(self):
        """Get the current rent amount set on the apartment unit"""
        return self.apartment_unit.rent_amount if self.apartment_unit else Decimal('0.00')
    
    @property
    def status(self):
        """Get the actual status of the payment schedule based on dates and is_active flag"""
        from django.utils import timezone
        today = timezone.now().date()
        
        if not self.is_active:
            return "Inactive"
        
        if self.start_date > today:
            return "Pending Start"
        
        if self.end_date and self.end_date < today:
            return "Expired"
        
        return "Active"
    
    @property
    def status_class(self):
        """Get CSS class for status display"""
        status = self.status
        if status == "Active":
            return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
        elif status == "Pending Start":
            return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
        elif status == "Expired":
            return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
        else:  # Inactive
            return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
    
    def save(self, *args, **kwargs):
        # If no rent_amount is set, use the apartment unit's rent amount
        if not self.rent_amount and self.apartment_unit:
            self.rent_amount = self.apartment_unit.rent_amount
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.tenant.username} - {self.apartment_unit} - ${self.rent_amount}"
    
    class Meta:
        ordering = ['-created_at']


class RentPayment(models.Model):
    """Records individual rent payments made by tenants"""
    
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"
    
    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        CHECK = "CHECK", "Check"
        BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"
        ONLINE_PORTAL = "ONLINE_PORTAL", "Online Portal"
        OTHER = "OTHER", "Other"
    
    payment_schedule = models.ForeignKey(
        PaymentSchedule,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    reference_number = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(blank=True)
    late_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_payments"
    )
    
    @property
    def total_amount_due(self):
        amount = self.amount_due or Decimal('0.00')
        late_fee = self.late_fee or Decimal('0.00')
        return amount + late_fee
    
    @property
    def balance_remaining(self):
        total = self.total_amount_due
        paid = self.amount_paid or Decimal('0.00')
        return total - paid
    
    @property
    def is_overdue(self):
        from django.utils import timezone
        if not self.due_date:
            return False
        return self.due_date < timezone.now().date() and self.status in ['PENDING', 'PARTIAL']
    
    def __str__(self):
        tenant_name = self.payment_schedule.tenant.username if self.payment_schedule else "No Schedule"
        due_date = self.due_date or "No Date"
        amount = self.amount_due or Decimal('0.00')
        return f"{tenant_name} - {due_date} - ${amount}"
    
    class Meta:
        ordering = ['-due_date']


class ExpenseRecord(models.Model):
    """Records expenses for property management"""
    
    class Category(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        UTILITIES = "UTILITIES", "Utilities"
        INSURANCE = "INSURANCE", "Insurance"
        TAXES = "TAXES", "Property Taxes"
        MANAGEMENT = "MANAGEMENT", "Management Fees"
        ADVERTISING = "ADVERTISING", "Advertising"
        LEGAL = "LEGAL", "Legal Fees"
        SUPPLIES = "SUPPLIES", "Supplies"
        LANDSCAPING = "LANDSCAPING", "Landscaping"
        CLEANING = "CLEANING", "Cleaning"
        OTHER = "OTHER", "Other"
    
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="expenses"
    )
    apartment_unit = models.ForeignKey(
        "properties.ApartmentUnit",
        on_delete=models.CASCADE,
        related_name="expenses",
        null=True,
        blank=True
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    expense_date = models.DateField()
    vendor = models.CharField(max_length=255, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_expenses"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Link to maintenance request if applicable
    maintenance_request = models.ForeignKey(
        "maintenance.MaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses"
    )
    
    def __str__(self):
        unit_info = f" - {self.apartment_unit}" if self.apartment_unit else ""
        return f"{self.property}{unit_info} - {self.category} - ${self.amount}"
    
    class Meta:
        ordering = ['-expense_date']


class PaymentReceipt(models.Model):
    """Stores receipt information for rent payments"""
    
    payment = models.OneToOneField(
        RentPayment,
        on_delete=models.CASCADE,
        related_name="receipt"
    )
    receipt_number = models.CharField(max_length=100, unique=True)
    receipt_file = models.FileField(
        upload_to='financial_receipts/',
        null=True,
        blank=True
    )
    issued_date = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="issued_receipts"
    )
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"REC-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.payment}"
