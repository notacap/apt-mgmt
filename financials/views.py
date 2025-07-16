from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from .models import PaymentSchedule, RentPayment, ExpenseRecord, PaymentReceipt
from .forms import (
    PaymentScheduleForm, RentPaymentForm, ExpenseRecordForm, 
    TenantPaymentForm, PaymentFilterForm, ExpenseFilterForm
)
from properties.models import ApartmentUnit
from communication.models import Notification
from datetime import datetime, timedelta
from decimal import Decimal


# ===== PAYMENT SCHEDULING VIEWS - DISABLED =====
# These views are currently disabled as payment scheduling is not needed for the current implementation.
# Payment schedules can be created and managed directly through Django admin if needed.

@login_required
def payment_schedule_list(request):
    """List all payment schedules for landlords/employees - DISABLED"""
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:dashboard_redirect')
    
    schedules = PaymentSchedule.objects.filter(
        apartment_unit__property__company=request.user.company
    )
    
    if request.user.property:
        schedules = schedules.filter(apartment_unit__property=request.user.property)
    
    paginator = Paginator(schedules, 20)
    page = request.GET.get('page')
    schedules = paginator.get_page(page)
    
    context = {
        'schedules': schedules,
        'page_title': 'Payment Schedules'
    }
    return render(request, 'financials/payment_schedule_list.html', context)


@login_required
def create_payment_schedule(request):
    """Create a new payment schedule"""
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to create payment schedules.")
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        form = PaymentScheduleForm(request.POST, user=request.user)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f"Payment schedule created for {schedule.tenant.username}")
            return redirect('financials:payment_schedule_detail', pk=schedule.pk)
    else:
        form = PaymentScheduleForm(user=request.user)
    
    context = {
        'form': form,
        'page_title': 'Create Payment Schedule'
    }
    return render(request, 'financials/create_payment_schedule.html', context)


@login_required
def payment_schedule_detail(request, pk):
    """View payment schedule details"""
    schedule = get_object_or_404(PaymentSchedule, pk=pk)
    
    # Check permissions
    if request.user.role == 'TENANT':
        if schedule.tenant != request.user:
            messages.error(request, "You don't have permission to view this schedule.")
            return redirect('core:dashboard_redirect')
    elif request.user.role in ['LANDLORD', 'EMPLOYEE']:
        if schedule.apartment_unit.property.company != request.user.company:
            messages.error(request, "You don't have permission to view this schedule.")
            return redirect('core:dashboard_redirect')
        if request.user.property and schedule.apartment_unit.property != request.user.property:
            messages.error(request, "You don't have permission to view this schedule.")
            return redirect('core:dashboard_redirect')
    
    # Get recent payments
    recent_payments = schedule.payments.all()[:10]
    
    context = {
        'schedule': schedule,
        'recent_payments': recent_payments,
        'page_title': f'Payment Schedule - {schedule.tenant.username}'
    }
    return render(request, 'financials/payment_schedule_detail.html', context)


@login_required
def edit_payment_schedule(request, pk):
    """Edit payment schedule"""
    schedule = get_object_or_404(PaymentSchedule, pk=pk)
    
    # Check permissions
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to edit payment schedules.")
        return redirect('core:dashboard_redirect')
    
    if schedule.apartment_unit.property.company != request.user.company:
        messages.error(request, "You don't have permission to edit this schedule.")
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        form = PaymentScheduleForm(request.POST, instance=schedule, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Payment schedule updated successfully.")
            return redirect('financials:payment_schedule_detail', pk=schedule.pk)
    else:
        form = PaymentScheduleForm(instance=schedule, user=request.user)
    
    context = {
        'form': form,
        'schedule': schedule,
        'page_title': f'Edit Payment Schedule - {schedule.tenant.username}'
    }
    return render(request, 'financials/edit_payment_schedule.html', context)


@login_required
def delete_payment_schedule(request, pk):
    """Delete payment schedule"""
    schedule = get_object_or_404(PaymentSchedule, pk=pk)
    
    # Check permissions
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to delete payment schedules.")
        return redirect('core:dashboard_redirect')
    
    if schedule.apartment_unit.property.company != request.user.company:
        messages.error(request, "You don't have permission to delete this schedule.")
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, "Payment schedule deleted successfully.")
        return redirect('financials:payment_schedule_list')
    
    context = {
        'schedule': schedule,
        'page_title': f'Delete Payment Schedule - {schedule.tenant.username}'
    }
    return render(request, 'financials/delete_payment_schedule.html', context)


@login_required
def payment_list(request):
    """List all rent payments for landlords/employees"""
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:dashboard_redirect')
    
    payments = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company
    )
    
    if request.user.property:
        payments = payments.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    # Apply filters
    filter_form = PaymentFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['status']:
            payments = payments.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data['payment_method']:
            payments = payments.filter(payment_method=filter_form.cleaned_data['payment_method'])
        if filter_form.cleaned_data['date_from']:
            payments = payments.filter(due_date__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data['date_to']:
            payments = payments.filter(due_date__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data['search']:
            search = filter_form.cleaned_data['search']
            payments = payments.filter(
                Q(payment_schedule__tenant__username__icontains=search) |
                Q(payment_schedule__apartment_unit__unit_number__icontains=search) |
                Q(reference_number__icontains=search)
            )
    
    paginator = Paginator(payments, 20)
    page = request.GET.get('page')
    payments = paginator.get_page(page)
    
    context = {
        'payments': payments,
        'filter_form': filter_form,
        'page_title': 'Rent Payments'
    }
    return render(request, 'financials/payment_list.html', context)


@login_required
def payment_detail(request, pk):
    """View payment details"""
    payment = get_object_or_404(RentPayment, pk=pk)
    
    # Check permissions
    if request.user.role == 'TENANT':
        if payment.payment_schedule.tenant != request.user:
            messages.error(request, "You don't have permission to view this payment.")
            return redirect('core:dashboard_redirect')
    elif request.user.role in ['LANDLORD', 'EMPLOYEE']:
        if payment.payment_schedule.apartment_unit.property.company != request.user.company:
            messages.error(request, "You don't have permission to view this payment.")
            return redirect('core:dashboard_redirect')
    
    context = {
        'payment': payment,
        'page_title': f'Payment Details - {payment.due_date}'
    }
    return render(request, 'financials/payment_detail.html', context)


@login_required
def process_payment(request, pk):
    """Process a payment (for landlords/employees)"""
    payment = get_object_or_404(RentPayment, pk=pk)
    
    # Check permissions
    if request.user.role not in ['LANDLORD', 'EMPLOYEE']:
        messages.error(request, "You don't have permission to process payments.")
        return redirect('core:dashboard_redirect')
    
    if payment.payment_schedule.apartment_unit.property.company != request.user.company:
        messages.error(request, "You don't have permission to process this payment.")
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        form = RentPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.processed_by = request.user
            
            # Update status based on amount paid
            if payment.amount_paid >= payment.total_amount_due:
                payment.status = 'PAID'
            elif payment.amount_paid > 0:
                payment.status = 'PARTIAL'
            
            payment.save()
            
            # Create notification for tenant
            Notification.objects.create(
                user=payment.payment_schedule.tenant,
                notification_type='PAYMENT_PROCESSED',
                title='Payment Processed',
                message=f'Your payment of ${payment.amount_paid} has been processed.',
                property=payment.payment_schedule.apartment_unit.property
            )
            
            messages.success(request, "Payment processed successfully.")
            return redirect('financials:payment_detail', pk=payment.pk)
    else:
        form = RentPaymentForm(instance=payment)
    
    context = {
        'form': form,
        'payment': payment,
        'page_title': f'Process Payment - {payment.due_date}'
    }
    return render(request, 'financials/process_payment.html', context)


@login_required
def tenant_payments(request):
    """Tenant view of their own payments"""
    if request.user.role != 'TENANT':
        messages.error(request, "This page is only accessible to tenants.")
        return redirect('core:dashboard_redirect')
    
    payments = RentPayment.objects.filter(
        payment_schedule__tenant=request.user
    ).order_by('-due_date')
    
    # Get payment schedule
    schedule = None
    if request.user.payment_schedules.exists():
        schedule = request.user.payment_schedules.first()
    
    context = {
        'payments': payments,
        'schedule': schedule,
        'page_title': 'My Rent Payments'
    }
    return render(request, 'financials/tenant_payments.html', context)


@login_required
def payment_portal(request):
    """Payment portal for tenants to make payments"""
    if request.user.role != 'TENANT':
        messages.error(request, "This page is only accessible to tenants.")
        return redirect('core:dashboard_redirect')
    
    # Get current/upcoming payment
    current_payment = None
    payment_schedule = None
    upcoming_payments = []
    
    if request.user.payment_schedules.exists():
        payment_schedule = request.user.payment_schedules.first()
        # Get the most recent unpaid or partially paid payment
        current_payment = RentPayment.objects.filter(
            payment_schedule=payment_schedule,
            status__in=['PENDING', 'OVERDUE', 'PARTIAL']
        ).order_by('due_date').first()
        
        # Get upcoming payments
        upcoming_payments = RentPayment.objects.filter(
            payment_schedule=payment_schedule,
            status__in=['PENDING', 'OVERDUE', 'PARTIAL']
        ).order_by('due_date')[:3]
    
    context = {
        'current_payment': current_payment,
        'payment_schedule': payment_schedule,
        'upcoming_payments': upcoming_payments,
        'page_title': 'Make a Payment'
    }
    return render(request, 'financials/payment_portal.html', context)


@login_required
def tenant_make_payment(request, pk):
    """Tenant submits payment information"""
    payment = get_object_or_404(RentPayment, pk=pk)
    
    # Check permissions
    if request.user.role != 'TENANT' or payment.payment_schedule.tenant != request.user:
        messages.error(request, "You don't have permission to make this payment.")
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        form = TenantPaymentForm(request.POST)
        if form.is_valid():
            payment.amount_paid = form.cleaned_data['amount_paid']
            payment.payment_date = form.cleaned_data['payment_date']
            payment.payment_method = form.cleaned_data['payment_method']
            payment.reference_number = form.cleaned_data['reference_number']
            payment.notes = form.cleaned_data['notes']
            payment.status = 'PENDING'  # Needs landlord approval
            payment.save()
            
            # Notify landlord/employees
            property_managers = payment.payment_schedule.apartment_unit.property.users.filter(
                role__in=['LANDLORD', 'EMPLOYEE']
            )
            for manager in property_managers:
                Notification.objects.create(
                    user=manager,
                    notification_type='PAYMENT_SUBMITTED',
                    title='Payment Submitted',
                    message=f'Payment of ${payment.amount_paid} submitted by {payment.payment_schedule.tenant.username}',
                    property=payment.payment_schedule.apartment_unit.property
                )
            
            messages.success(request, "Payment submitted successfully. It will be reviewed by your landlord.")
            return redirect('financials:tenant_payments')
    else:
        form = TenantPaymentForm()
    
    context = {
        'form': form,
        'payment': payment,
        'page_title': f'Make Payment - {payment.due_date}'
    }
    return render(request, 'financials/tenant_make_payment.html', context)


# Expense-related views will be implemented next
def expense_list(request):
    # Placeholder
    pass

def create_expense(request):
    # Placeholder
    pass

def expense_detail(request, pk):
    # Placeholder
    pass

def edit_expense(request, pk):
    # Placeholder
    pass

def delete_expense(request, pk):
    # Placeholder
    pass

def generate_receipt(request, payment_id):
    # Placeholder
    pass

def download_receipt(request, payment_id):
    # Placeholder
    pass

def units_by_property(request):
    # Placeholder for HTMX
    pass

def financial_reports(request):
    # Placeholder
    pass

def income_report(request):
    # Placeholder
    pass

def expense_report(request):
    # Placeholder
    pass
