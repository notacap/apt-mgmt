from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q, Count
from users.forms import LandlordCreationForm, InvitationForm, UserProfileForm, InvitationAcceptanceForm, EmployeeManagementForm
from users.models import User, Invitation
from django.contrib.auth.models import Group
from documents.models import Document, DocumentShare
from maintenance.models import MaintenanceRequest, MaintenanceInvoice, MaintenanceCategory
from communication.models import MessageThread, Message, MessageReadStatus, Notification
from properties.models import ApartmentUnit
from financials.models import PaymentSchedule, RentPayment, ExpenseRecord
from events.models import CalendarEvent, WorkSchedule
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Sum, Q, Avg, Count
from decimal import Decimal
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings

# Create your views here.

def index(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard_redirect")
    return redirect("core:login")

@login_required
def landlord_dashboard(request):
    """Landlord dashboard with real document and maintenance data"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access the dashboard.")
        return redirect("core:login")
    
    # Get company-wide document data
    company_documents = Document.objects.filter(
        company=request.user.company,
        is_active=True
    )
    
    # Recent documents (last 30 days)
    recent_cutoff = timezone.now() - timedelta(days=30)
    recent_documents = company_documents.filter(
        created_at__gte=recent_cutoff
    ).order_by('-created_at')[:5]
    
    # Document counts by access level
    company_doc_count = company_documents.filter(access_level=Document.AccessLevel.COMPANY).count()
    property_doc_count = company_documents.filter(access_level=Document.AccessLevel.PROPERTY).count()
    private_doc_count = company_documents.filter(access_level=Document.AccessLevel.PRIVATE).count()
    
    # Document sharing stats
    shared_with_employees = DocumentShare.objects.filter(
        document__company=request.user.company,
        shared_with__role='EMPLOYEE'
    ).count()
    
    shared_with_tenants = DocumentShare.objects.filter(
        document__company=request.user.company,
        shared_with__role='TENANT'
    ).count()
    
    # Maintenance request data
    company_maintenance_requests = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        company_maintenance_requests = company_maintenance_requests.filter(
            property=request.user.property
        )
    
    # Maintenance statistics (exclude completed requests from total)
    active_maintenance_requests = company_maintenance_requests.exclude(status='COMPLETED')
    total_maintenance_requests = active_maintenance_requests.count()
    pending_requests = company_maintenance_requests.filter(status='SUBMITTED').count()
    in_progress_requests = company_maintenance_requests.filter(status='IN_PROGRESS').count()
    emergency_requests = active_maintenance_requests.filter(priority='EMERGENCY').count()
    completed_this_month = company_maintenance_requests.filter(
        status='COMPLETED',
        completed_at__gte=timezone.now().replace(day=1)
    ).count()
    
    # Recent maintenance requests
    recent_maintenance_requests = company_maintenance_requests.order_by('-created_at')[:5]
    
    # Recent message threads
    recent_message_threads = MessageThread.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]
    
    # Financial calculations - Calculate based on occupied units' rent amounts
    # Define date ranges first
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get occupied apartment units for the company
    occupied_units_query = ApartmentUnit.objects.filter(
        property__company=request.user.company,
        is_occupied=True
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        occupied_units_query = occupied_units_query.filter(
            property=request.user.property
        )
    
    # Calculate current month potential income (sum of rent amounts for occupied units)
    current_month_income = occupied_units_query.aggregate(
        total=Sum('rent_amount')
    )['total'] or Decimal('0.00')
    
    # For now, set last month income same as current (since we're showing potential income)
    # In the future, this could track historical changes
    last_month_income = current_month_income
    income_change_percent = 0  # No change for now since we're showing potential income
    
    # Get expense data for the current month from two sources:
    # 1. ExpenseRecord objects
    expense_query = ExpenseRecord.objects.filter(
        property__company=request.user.company,
        expense_date__gte=current_month_start,
        expense_date__lt=current_month_start + timedelta(days=32)
    )
    
    if request.user.property:
        expense_query = expense_query.filter(property=request.user.property)
    
    expense_records_total = expense_query.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # 2. MaintenanceInvoice objects
    maintenance_invoice_query = MaintenanceInvoice.objects.filter(
        maintenance_request__property__company=request.user.company,
        invoice_date__gte=current_month_start,
        invoice_date__lt=current_month_start + timedelta(days=32)
    )
    
    if request.user.property:
        maintenance_invoice_query = maintenance_invoice_query.filter(
            maintenance_request__property=request.user.property
        )
    
    maintenance_invoices_total = maintenance_invoice_query.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    # Total expenses = expense records + maintenance invoices
    current_month_expenses = expense_records_total + maintenance_invoices_total
    
    # Calculate net revenue
    current_month_revenue = current_month_income - current_month_expenses
    
    # Calculate payment status metrics
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Get current month rent payments
    current_month_rent_payments = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company,
        due_date__gte=current_month_start,
        due_date__lte=current_month_end
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        current_month_rent_payments = current_month_rent_payments.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    # Calculate payment status statistics
    total_current_payments = current_month_rent_payments.count()
    paid_payments = current_month_rent_payments.filter(status='PAID').count()
    overdue_payments = current_month_rent_payments.filter(status='OVERDUE').count()
    pending_payments = current_month_rent_payments.filter(status='PENDING').count()
    partial_payments = current_month_rent_payments.filter(status='PARTIAL').count()
    
    # Calculate on-time payment percentage
    if total_current_payments > 0:
        on_time_percentage = round((paid_payments / total_current_payments) * 100)
    else:
        on_time_percentage = 0
    
    # Count tenants with late/overdue payments
    late_tenants = current_month_rent_payments.filter(
        status__in=['OVERDUE', 'PARTIAL']
    ).values('payment_schedule__tenant').distinct().count()
    
    # Calculate occupancy rate metrics
    all_units_query = ApartmentUnit.objects.filter(
        property__company=request.user.company
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        all_units_query = all_units_query.filter(
            property=request.user.property
        )
    
    total_units_count = all_units_query.count()
    
    # Count units that have tenants assigned (more accurate than is_occupied flag)
    occupied_units_count = all_units_query.filter(tenant__isnull=False).distinct().count()
    vacant_units_count = total_units_count - occupied_units_count
    
    # Calculate occupancy percentage
    if total_units_count > 0:
        occupancy_percentage = round((occupied_units_count / total_units_count) * 100)
    else:
        occupancy_percentage = 0
    
    # Calculate lease expiration metrics
    lease_schedules_query = PaymentSchedule.objects.filter(
        apartment_unit__property__company=request.user.company,
        is_active=True,
        end_date__isnull=False
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        lease_schedules_query = lease_schedules_query.filter(
            apartment_unit__property=request.user.property
        )
    
    today = timezone.now().date()
    
    # Count leases expiring in next 30, 60, and 90 days
    leases_expiring_30_days = lease_schedules_query.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30)
    ).count()
    
    leases_expiring_90_days = lease_schedules_query.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=90)
    ).count()
    
    # Calculate average vacancy duration for vacant units
    vacant_units_for_avg = ApartmentUnit.objects.filter(
        property__company=request.user.company,
        tenant__isnull=True
    )
    
    # Filter by property if landlord is assigned to specific property
    if request.user.property:
        vacant_units_for_avg = vacant_units_for_avg.filter(
            property=request.user.property
        )
    
    # Calculate average vacancy days (estimate based on last updated)
    avg_vacancy_days = 0
    if vacant_units_count > 0:
        vacancy_durations = []
        for unit in vacant_units_for_avg:
            if unit.updated_at:
                days_vacant = (timezone.now() - unit.updated_at).days
                vacancy_durations.append(days_vacant)
        
        if vacancy_durations:
            avg_vacancy_days = sum(vacancy_durations) // len(vacancy_durations)
    
    # Get available properties for the property selector
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Get selected property from URL parameter
    selected_property_id = request.GET.get('property')
    selected_property = None
    if selected_property_id:
        try:
            selected_property = Property.objects.get(
                id=selected_property_id,
                company=request.user.company
            )
            # Recalculate metrics for the selected property
            occupied_units_query = ApartmentUnit.objects.filter(
                property=selected_property,
                is_occupied=True
            )
            current_month_income = occupied_units_query.aggregate(
                total=Sum('rent_amount')
            )['total'] or Decimal('0.00')
            
            # Recalculate expenses for selected property
            expense_query = ExpenseRecord.objects.filter(
                property=selected_property,
                expense_date__gte=current_month_start,
                expense_date__lt=current_month_start + timedelta(days=32)
            )
            expense_records_total = expense_query.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            maintenance_invoice_query = MaintenanceInvoice.objects.filter(
                maintenance_request__property=selected_property,
                invoice_date__gte=current_month_start,
                invoice_date__lt=current_month_start + timedelta(days=32)
            )
            maintenance_invoices_total = maintenance_invoice_query.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            current_month_expenses = expense_records_total + maintenance_invoices_total
            current_month_revenue = current_month_income - current_month_expenses
            
            # Recalculate maintenance requests for selected property
            company_maintenance_requests = MaintenanceRequest.objects.filter(
                property=selected_property
            )
            active_maintenance_requests = company_maintenance_requests.exclude(status='COMPLETED')
            total_maintenance_requests = active_maintenance_requests.count()
            pending_requests = company_maintenance_requests.filter(status='SUBMITTED').count()
            in_progress_requests = company_maintenance_requests.filter(status='IN_PROGRESS').count()
            emergency_requests = active_maintenance_requests.filter(priority='EMERGENCY').count()
            completed_this_month = company_maintenance_requests.filter(
                status='COMPLETED',
                completed_at__gte=timezone.now().replace(day=1)
            ).count()
            recent_maintenance_requests = company_maintenance_requests.order_by('-created_at')[:5]
            
            # Recalculate payment status for selected property
            current_month_rent_payments = RentPayment.objects.filter(
                payment_schedule__apartment_unit__property=selected_property,
                due_date__gte=current_month_start,
                due_date__lte=current_month_end
            )
            
            total_current_payments = current_month_rent_payments.count()
            paid_payments = current_month_rent_payments.filter(status='PAID').count()
            overdue_payments = current_month_rent_payments.filter(status='OVERDUE').count()
            pending_payments = current_month_rent_payments.filter(status='PENDING').count()
            partial_payments = current_month_rent_payments.filter(status='PARTIAL').count()
            
            if total_current_payments > 0:
                on_time_percentage = round((paid_payments / total_current_payments) * 100)
            else:
                on_time_percentage = 0
            
            late_tenants = current_month_rent_payments.filter(
                status__in=['OVERDUE', 'PARTIAL']
            ).values('payment_schedule__tenant').distinct().count()
            
            # Recalculate occupancy rate for selected property
            all_units_query = ApartmentUnit.objects.filter(
                property=selected_property
            )
            total_units_count = all_units_query.count()
            # Count units with tenants (more accurate than is_occupied flag)
            occupied_units_count = all_units_query.filter(tenant__isnull=False).distinct().count()
            vacant_units_count = total_units_count - occupied_units_count
            
            if total_units_count > 0:
                occupancy_percentage = round((occupied_units_count / total_units_count) * 100)
            else:
                occupancy_percentage = 0
            
            # Recalculate lease expirations for selected property
            lease_schedules_query = PaymentSchedule.objects.filter(
                apartment_unit__property=selected_property,
                is_active=True,
                end_date__isnull=False
            )
            
            leases_expiring_30_days = lease_schedules_query.filter(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30)
            ).count()
            
            leases_expiring_90_days = lease_schedules_query.filter(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=90)
            ).count()
            
            # Recalculate average vacancy for selected property
            vacant_units_for_avg = ApartmentUnit.objects.filter(
                property=selected_property,
                tenant__isnull=True
            )
            
            avg_vacancy_days = 0
            if vacant_units_count > 0:
                vacancy_durations = []
                for unit in vacant_units_for_avg:
                    if unit.updated_at:
                        days_vacant = (timezone.now() - unit.updated_at).days
                        vacancy_durations.append(days_vacant)
                
                if vacancy_durations:
                    avg_vacancy_days = sum(vacancy_durations) // len(vacancy_durations)
            
        except Property.DoesNotExist:
            selected_property = None
    
    # Get tenant data for Tenant Management card
    tenant_query = User.objects.filter(
        company=request.user.company,
        role=User.Role.TENANT
    ).select_related('apartment_unit', 'apartment_unit__property')
    
    # Apply property filter for tenants
    if selected_property:
        tenant_query = tenant_query.filter(apartment_unit__property=selected_property)
    elif request.user.property:
        tenant_query = tenant_query.filter(apartment_unit__property=request.user.property)
    
    # Get recent tenants with lease information (for display in the card)
    recent_tenants_raw = tenant_query.order_by('-date_joined')[:3]
    
    # Annotate tenants with lease information
    recent_tenants = []
    for tenant in recent_tenants_raw:
        lease_info = {
            'tenant': tenant,
            'lease_end_date': None,
            'lease_status': 'no_lease',
            'days_until_expiration': None
        }
        
        # Debug: Let's check what payment schedules exist for this tenant
        all_schedules = PaymentSchedule.objects.filter(tenant=tenant)
        print(f"DEBUG: Tenant {tenant.username} has {all_schedules.count()} payment schedules")
        for schedule in all_schedules:
            print(f"  - Schedule: {schedule.apartment_unit}, Active: {schedule.is_active}, End Date: {schedule.end_date}")
        
        # Try finding by tenant only first (more lenient)
        active_lease = PaymentSchedule.objects.filter(
            tenant=tenant,
            is_active=True,
            end_date__isnull=False
        ).first()
        
        if active_lease and active_lease.end_date:
                lease_info['lease_end_date'] = active_lease.end_date
                days_until_expiration = (active_lease.end_date - today).days
                lease_info['days_until_expiration'] = days_until_expiration
                
                if active_lease.end_date < today:
                    lease_info['lease_status'] = 'expired'
                elif days_until_expiration <= 30:
                    lease_info['lease_status'] = 'expiring_soon'
                else:
                    lease_info['lease_status'] = 'active'
        
        recent_tenants.append(lease_info)
    
    # Calculate tenant stats
    total_tenant_count = tenant_query.count()
    tenants_with_expiring_leases = 0
    
    # Check for expiring leases in the next 30 days
    today = timezone.now().date()
    for tenant in tenant_query:
        if tenant.apartment_unit:
            active_lease = PaymentSchedule.objects.filter(
                tenant=tenant,
                apartment_unit=tenant.apartment_unit,
                is_active=True,
                end_date__isnull=False,
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30)
            ).first()
            if active_lease:
                tenants_with_expiring_leases += 1
    
    # Get employee data for the Employee Management card
    employee_query = User.objects.filter(
        company=request.user.company,
        role=User.Role.EMPLOYEE
    ).select_related('property')
    
    # Apply property filter for employees if one is selected
    if selected_property:
        employee_query = employee_query.filter(property=selected_property)
    elif request.user.property:
        employee_query = employee_query.filter(property=request.user.property)
    
    # Get recent employees (for display in the card)
    recent_employees = employee_query.order_by('-date_joined')[:3]
    
    # Calculate employee stats
    total_employee_count = employee_query.count()
    company_wide_employees = User.objects.filter(
        company=request.user.company,
        role=User.Role.EMPLOYEE
    ).count()
    employees_by_property = employee_query.exclude(property__isnull=True).values('property__name').annotate(
        count=Count('id')
    ).order_by('property__name')
    
    # Recent hires in last 30 days
    recent_cutoff = timezone.now() - timedelta(days=30)
    recent_employee_hires = employee_query.filter(date_joined__gte=recent_cutoff).count()
    
    context = {
        'recent_documents': recent_documents,
        'company_doc_count': company_doc_count,
        'property_doc_count': property_doc_count,
        'private_doc_count': private_doc_count,
        'shared_with_employees': shared_with_employees,
        'shared_with_tenants': shared_with_tenants,
        'total_documents': company_documents.count(),
        # Maintenance data
        'total_maintenance_requests': total_maintenance_requests,
        'pending_requests': pending_requests,
        'in_progress_requests': in_progress_requests,
        'emergency_requests': emergency_requests,
        'completed_this_month': completed_this_month,
        'recent_maintenance_requests': recent_maintenance_requests,
        # Communication data
        'recent_message_threads': recent_message_threads,
        # Financial data
        'current_month_income': current_month_income,
        'last_month_income': last_month_income,
        'income_change_percent': income_change_percent,
        'current_month_expenses': current_month_expenses,
        'current_month_revenue': current_month_revenue,
        'expense_records_total': expense_records_total if 'expense_records_total' in locals() else Decimal('0.00'),
        'maintenance_invoices_total': maintenance_invoices_total if 'maintenance_invoices_total' in locals() else Decimal('0.00'),
        # Payment status data
        'on_time_percentage': on_time_percentage,
        'total_current_payments': total_current_payments,
        'paid_payments': paid_payments,
        'overdue_payments': overdue_payments,
        'pending_payments': pending_payments,
        'partial_payments': partial_payments,
        'late_tenants': late_tenants,
        # Occupancy rate data
        'total_units_count': total_units_count,
        'occupied_units_count': occupied_units_count,
        'vacant_units_count': vacant_units_count,
        'occupancy_percentage': occupancy_percentage,
        # Lease expiration data
        'leases_expiring_30_days': leases_expiring_30_days,
        'leases_expiring_90_days': leases_expiring_90_days,
        # Vacant units data
        'avg_vacancy_days': avg_vacancy_days,
        # Property selection data
        'available_properties': available_properties,
        'selected_property': selected_property,
        # Tenant data
        'recent_tenants': recent_tenants,
        'total_tenant_count': total_tenant_count,
        'tenants_with_expiring_leases': tenants_with_expiring_leases,
        # Employee data
        'total_employee_count': total_employee_count,
        'recent_employees': recent_employees,
        'employees_by_property': employees_by_property,
        'recent_employee_hires': recent_employee_hires,
        'company_wide_employees': company_wide_employees,
    }
    
    return render(request, "dashboards/landlord.html", context)

@login_required
def employee_dashboard(request):
    """Employee dashboard with real document and maintenance data"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access the dashboard.")
        return redirect("core:login")
    
    # Get documents accessible to employee
    accessible_documents = Document.objects.filter(
        company=request.user.company,
        is_active=True
    )
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        property_documents = accessible_documents.filter(
            Q(access_level=Document.AccessLevel.COMPANY) |
            Q(access_level=Document.AccessLevel.PROPERTY, property=request.user.property) |
            Q(allowed_users=request.user)
        ).distinct()
    else:
        # Employee not assigned to specific property - show company-wide documents
        property_documents = accessible_documents.filter(
            Q(access_level=Document.AccessLevel.COMPANY) |
            Q(allowed_users=request.user)
        ).distinct()
    
    # Recent documents uploaded by employee
    employee_uploads = accessible_documents.filter(
        uploaded_by=request.user
    ).order_by('-created_at')[:5]
    
    # Recent documents shared with employee
    shared_documents = DocumentShare.objects.filter(
        shared_with=request.user
    ).order_by('-created_at')[:5]
    
    # Documents shared from landlord (company-wide access)
    landlord_shared = DocumentShare.objects.filter(
        shared_with=request.user,
        shared_by__role='LANDLORD'
    ).count()
    
    # Property-specific document count
    if request.user.property:
        property_doc_count = accessible_documents.filter(
            property=request.user.property
        ).count()
    else:
        property_doc_count = 0
    
    # Maintenance request data
    employee_maintenance_requests = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    )
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        employee_maintenance_requests = employee_maintenance_requests.filter(
            property=request.user.property
        )
    
    # Maintenance statistics for employee
    assigned_to_me = employee_maintenance_requests.filter(assigned_to=request.user).count()
    pending_assignments = employee_maintenance_requests.filter(
        status='SUBMITTED',
        assigned_to__isnull=True
    ).count()
    in_progress_assigned = employee_maintenance_requests.filter(
        assigned_to=request.user,
        status='IN_PROGRESS'
    ).count()
    emergency_requests = employee_maintenance_requests.filter(priority='EMERGENCY').count()
    
    # Recent maintenance requests assigned to employee
    my_assigned_requests = employee_maintenance_requests.filter(
        assigned_to=request.user
    ).order_by('-created_at')[:5]
    
    # Recent message threads
    recent_message_threads = MessageThread.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]
    
    # Calendar events for today
    today = timezone.localtime().date()
    today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    today_end = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.max.time()))
    
    # Get today's calendar events assigned to employee
    todays_events_query = CalendarEvent.objects.filter(
        assigned_to=request.user,
        start_datetime__gte=today_start,
        start_datetime__lte=today_end,
        is_cancelled=False
    ).select_related('property', 'apartment_unit', 'maintenance_request')
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        todays_events_query = todays_events_query.filter(property=request.user.property)
    
    todays_events = todays_events_query.order_by('start_datetime')
    todays_events_count = todays_events.count()
    
    # Get sample of today's events for display
    todays_events_sample = todays_events[:3]
    
    context = {
        'employee_uploads': employee_uploads,
        'shared_documents': shared_documents,
        'property_documents': property_documents[:5],  # Limit for display
        'landlord_shared_count': landlord_shared,
        'property_doc_count': property_doc_count,
        'total_accessible': property_documents.count(),
        'user_property': request.user.property,
        # Maintenance data
        'assigned_to_me': assigned_to_me,
        'pending_assignments': pending_assignments,
        'in_progress_assigned': in_progress_assigned,
        'emergency_requests': emergency_requests,
        'my_assigned_requests': my_assigned_requests,
        # Communication data
        'recent_message_threads': recent_message_threads,
        # Calendar data
        'todays_events_count': todays_events_count,
        'todays_events_sample': todays_events_sample,
    }
    
    return render(request, "dashboards/employee.html", context)

@login_required
def tenant_dashboard(request):
    """Tenant dashboard with real document and maintenance data"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access the dashboard.")
        return redirect("core:login")
    
    # Get tenant's personal documents
    personal_documents = Document.objects.filter(
        company=request.user.company,
        uploaded_by=request.user,
        is_active=True
    ).order_by('-created_at')[:5]
    
    # Get documents shared with tenant
    shared_documents = DocumentShare.objects.filter(
        shared_with=request.user
    ).select_related('document', 'shared_by').order_by('-created_at')[:5]
    
    # Get community notices (documents accessible company-wide or shared specifically)
    accessible_documents = Document.objects.filter(
        company=request.user.company,
        is_active=True
    )
    
    # Filter documents tenant can access
    community_documents = []
    for doc in accessible_documents:
        if doc.is_accessible_by_user(request.user) and doc.uploaded_by != request.user:
            community_documents.append(doc)
    
    # Limit community documents for display
    community_documents = community_documents[:5]
    
    # Get counts
    personal_doc_count = Document.objects.filter(
        company=request.user.company,
        uploaded_by=request.user,
        is_active=True
    ).count()
    
    shared_with_tenant_count = DocumentShare.objects.filter(
        shared_with=request.user
    ).count()
    
    # Recent shares (new documents shared with tenant)
    recent_shares = DocumentShare.objects.filter(
        shared_with=request.user,
        is_read=False
    ).count()
    
    # Maintenance request data for tenant
    tenant_maintenance_requests = MaintenanceRequest.objects.filter(
        tenant=request.user
    )
    
    # Maintenance statistics for tenant
    total_my_requests = tenant_maintenance_requests.count()
    open_requests = tenant_maintenance_requests.exclude(status='COMPLETED').count()
    in_progress_requests = tenant_maintenance_requests.filter(status='IN_PROGRESS').count()
    completed_requests = tenant_maintenance_requests.filter(status='COMPLETED').count()
    
    # Recent maintenance requests by tenant
    recent_maintenance_requests = tenant_maintenance_requests.order_by('-created_at')[:3]
    
    # Recent message threads
    recent_message_threads = MessageThread.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:5]
    
    # Rent status data for tenant
    current_schedule = PaymentSchedule.objects.filter(
        tenant=request.user,
        is_active=True
    ).select_related('apartment_unit', 'apartment_unit__property').first()
    
    # Calculate lease status
    lease_status = 'no_lease'
    days_until_lease_end = None
    lease_end_date = None
    
    if current_schedule and current_schedule.end_date:
        today = timezone.now().date()
        lease_end_date = current_schedule.end_date
        days_until_lease_end = (current_schedule.end_date - today).days
        
        if current_schedule.end_date < today:
            lease_status = 'expired'
        elif days_until_lease_end <= 30:
            lease_status = 'expiring_soon'
        else:
            lease_status = 'active'
    
    # Get next upcoming payment
    next_payment = RentPayment.objects.filter(
        payment_schedule__tenant=request.user,
        status__in=['PENDING'],
        due_date__gte=timezone.now().date()
    ).order_by('due_date').first()
    
    # If no next payment exists but we have a schedule, calculate the next due date
    next_due_date = None
    next_amount = None
    if not next_payment and current_schedule:
        today = timezone.now().date()
        
        # Calculate next payment due date based on schedule
        if current_schedule.frequency == 'MONTHLY':
            # Find next month's payment date
            year = today.year
            month = today.month
            day = current_schedule.payment_day
            
            # If this month's payment day hasn't passed, use this month
            if today.day <= day:
                next_due_date = date(year, month, day)
            else:
                # Move to next month
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                next_due_date = date(year, month, day)
            
            next_amount = current_schedule.rent_amount
    
    # Get recent payment status for display
    recent_payment = RentPayment.objects.filter(
        payment_schedule__tenant=request.user
    ).order_by('-due_date').first()
    
    # Count unread messages
    unread_message_count = 0
    total_message_count = 0
    for thread in recent_message_threads:
        total_message_count += 1
        # Calculate unread messages for this tenant
        # Check if there are messages in this thread that:
        # 1. Were not sent by the current user
        # 2. Have not been read by the current user (no MessageReadStatus record)
        unread_for_user = thread.messages.exclude(
            sender=request.user
        ).exclude(
            messagereadstatus__user=request.user
        ).count()
        if unread_for_user > 0:
            unread_message_count += 1
    
    context = {
        'personal_documents': personal_documents,
        'shared_documents': shared_documents,
        'community_documents': community_documents,
        'personal_doc_count': personal_doc_count,
        'shared_with_tenant_count': shared_with_tenant_count,
        'recent_shares_count': recent_shares,
        'user_property': request.user.property,
        # Maintenance data
        'total_my_requests': total_my_requests,
        'open_requests': open_requests,
        'in_progress_requests': in_progress_requests,
        'completed_requests': completed_requests,
        'recent_maintenance_requests': recent_maintenance_requests,
        # Communication data
        'recent_message_threads': recent_message_threads,
        'unread_message_count': unread_message_count,
        'total_message_count': total_message_count,
        # Rent status data
        'current_schedule': current_schedule,
        'lease_status': lease_status,
        'days_until_lease_end': days_until_lease_end,
        'lease_end_date': lease_end_date,
        'next_payment': next_payment,
        'next_due_date': next_due_date,
        'next_amount': next_amount,
        'recent_payment': recent_payment,
    }
    
    return render(request, "dashboards/tenant.html", context)

def create_landlord(request):
    if request.method == "POST":
        form = LandlordCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Landlord account created successfully.")
            return redirect("core:index")
    else:
        form = LandlordCreationForm()
    return render(request, "accounts/create_landlord.html", {"form": form})

@login_required
def send_invitation(request):
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")

    if request.method == "POST":
        form = InvitationForm(request.POST, user=request.user)
        if form.is_valid():
            invitation = form.save(commit=False)
            invitation.invited_by = request.user
            invitation.company = request.user.company
            invitation.save()
            
            # Send invitation email
            invitation_url = request.build_absolute_uri(f"/accept-invitation/{invitation.token}/")
            
            subject = f"Invitation to join {invitation.company.name}"
            
            if invitation.role == 'TENANT':
                role_info = f"as a Tenant for {invitation.property.name}"
                if invitation.apartment_unit:
                    role_info += f", Unit {invitation.apartment_unit.unit_number}"
            elif invitation.role == 'EMPLOYEE':
                if invitation.all_properties:
                    role_info = f"as an Employee with access to all properties"
                else:
                    role_info = f"as an Employee for {invitation.property.name}"
            else:
                role_info = f"as {invitation.get_role_display()}"
            
            message = f"""
You have been invited to join {invitation.company.name} {role_info}.

To accept this invitation and create your account, please click the link below:
{invitation_url}

This invitation was sent by {invitation.invited_by.get_full_name() or invitation.invited_by.username}.

If you did not expect this invitation, you can safely ignore this email.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [invitation.email],
                fail_silently=False,
            )
            
            messages.success(request, f"Invitation sent successfully to {invitation.email}.")
            return redirect("core:index")
    else:
        form = InvitationForm(user=request.user)
    return render(request, "accounts/send_invitation.html", {"form": form})

def accept_invitation(request, token):
    try:
        invitation = Invitation.objects.get(token=token, is_accepted=False)
    except Invitation.DoesNotExist:
        messages.error(request, "This invitation is invalid or has expired.")
        return redirect("core:login")

    if request.method == "POST":
        form = InvitationAcceptanceForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = invitation.email
            user.role = invitation.role
            user.company = invitation.company
            user.property = invitation.property
            # Set apartment unit for tenants
            if invitation.role == 'TENANT' and invitation.apartment_unit:
                user.apartment_unit = invitation.apartment_unit
            user.set_password(form.cleaned_data["password"])
            user.save()

            # Add user to the correct group
            group_name = f"{invitation.role.capitalize()}s"
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            
            # Handle tenant-specific setup
            if invitation.role == 'TENANT' and invitation.apartment_unit:
                # Mark the unit as occupied
                invitation.apartment_unit.is_occupied = True
                invitation.apartment_unit.save()
                
                # Create payment schedule using apartment unit's rent amount
                if invitation.lease_length_months:
                    start_date = invitation.lease_start_date or date.today()
                    # Calculate end date based on lease length
                    year = start_date.year
                    month = start_date.month + invitation.lease_length_months
                    while month > 12:
                        month -= 12
                        year += 1
                    end_date = date(year, month, start_date.day)
                    
                    PaymentSchedule.objects.create(
                        tenant=user,
                        apartment_unit=invitation.apartment_unit,
                        rent_amount=invitation.apartment_unit.rent_amount,  # Use apartment unit's rent amount
                        frequency='MONTHLY',
                        payment_day=invitation.rent_payment_date or 1,  # Use payment day from invitation or default to 1st
                        start_date=start_date,
                        end_date=end_date,
                        is_active=True
                    )
            
            # Handle employee-specific setup
            elif invitation.role == 'EMPLOYEE' and invitation.all_properties:
                # If employee has access to all properties, clear the specific property assignment
                user.property = None
                user.save()

            invitation.is_accepted = True
            invitation.save()
            
            messages.success(request, "Your account has been created! Please log in.")
            return redirect("core:login")
    else:
        form = InvitationAcceptanceForm()
        
    return render(request, "accounts/accept_invitation.html", {"form": form})

@login_required
def dashboard_redirect(request):
    user = request.user
    if user.role == "LANDLORD":
        return redirect("core:landlord_dashboard")
    elif user.role == "EMPLOYEE":
        return redirect("core:employee_dashboard")
    elif user.role == "TENANT":
        return redirect("core:tenant_dashboard")
    else:
        # Superusers and others can go to the admin or a default page
        return redirect("/admin")

@login_required
def profile(request):
    # Check if editing another user (employee management)
    user_id = request.GET.get('user')
    target_user = request.user
    is_employee_management = False
    
    if user_id and request.user.role == User.Role.LANDLORD:
        try:
            target_user = User.objects.get(
                id=user_id, 
                company=request.user.company,
                role=User.Role.EMPLOYEE
            )
            is_employee_management = True
        except User.DoesNotExist:
            messages.error(request, "Employee not found or access denied.")
            return redirect("core:employee_list")
    
    if request.method == "POST":
        if is_employee_management:
            form = EmployeeManagementForm(request.POST, instance=target_user, user=request.user)
            success_message = f"{target_user.get_full_name()}'s profile updated successfully."
            redirect_url = "core:employee_list"
        else:
            form = UserProfileForm(request.POST, instance=target_user)
            success_message = "Profile updated successfully."
            redirect_url = "core:profile"
            
        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect(redirect_url)
    else:
        if is_employee_management:
            form = EmployeeManagementForm(instance=target_user, user=request.user)
        else:
            form = UserProfileForm(instance=target_user)
    
    context = {
        "form": form,
        "target_user": target_user,
        "is_employee_management": is_employee_management,
    }
    return render(request, "accounts/profile.html", context)

@login_required
def get_available_units(request, property_id):
    """API endpoint to fetch available units for a property"""
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get unoccupied units for the property
    units = ApartmentUnit.objects.filter(
        property_id=property_id,
        property__company=request.user.company,
        is_occupied=False
    ).values('id', 'unit_number', 'bedrooms', 'bathrooms', 'rent_amount')
    
    return JsonResponse({'units': list(units)})

def custom_login(request):
    """Custom login view with specific error messages"""
    if request.user.is_authenticated:
        return redirect('core:dashboard_redirect')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if username and password:
            # Check if user exists
            try:
                user = User.objects.get(username=username)
                # User exists, try to authenticate
                authenticated_user = authenticate(request, username=username, password=password)
                
                if authenticated_user is not None:
                    login(request, authenticated_user)
                    next_url = request.GET.get('next', 'core:dashboard_redirect')
                    return redirect(next_url)
                else:
                    # Password is incorrect
                    form.is_valid()  # Trigger form validation
                    form.add_error('password', 'Incorrect password')
            except User.DoesNotExist:
                # User doesn't exist
                form.is_valid()  # Trigger form validation
                form.add_error('username', 'User doesn\'t exist')
        else:
            # Let the form handle its own validation for empty fields
            form.is_valid()
    else:
        form = AuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def rent_income_detail(request):
    """Detailed view for monthly rent income metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get property filter from URL parameter
    property_id = request.GET.get('property')
    selected_property = None
    
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Date range calculations
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = current_month_start - timedelta(days=1)
    
    # Base query for rent payments
    rent_payments_query = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company
    ).select_related(
        'payment_schedule__tenant',
        'payment_schedule__apartment_unit',
        'payment_schedule__apartment_unit__property'
    )
    
    # Apply property filter
    if selected_property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=selected_property
        )
    elif request.user.property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    # Current month payments
    current_month_payments = rent_payments_query.filter(
        due_date__gte=current_month_start,
        due_date__lte=current_month_end
    ).order_by('-due_date', 'payment_schedule__apartment_unit__unit_number')
    
    # Previous month payments for comparison
    last_month_payments = rent_payments_query.filter(
        due_date__gte=last_month_start,
        due_date__lte=last_month_end
    )
    
    # Calculate totals
    current_month_total = current_month_payments.filter(status='PAID').aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')
    
    current_month_pending = current_month_payments.filter(status='PENDING').aggregate(
        total=Sum('amount_due')
    )['total'] or Decimal('0.00')
    
    current_month_overdue = current_month_payments.filter(status='OVERDUE').aggregate(
        total=Sum('amount_due')
    )['total'] or Decimal('0.00')
    
    last_month_total = last_month_payments.filter(status='PAID').aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0.00')
    
    # Calculate percentage change
    if last_month_total > 0:
        income_change_percent = ((current_month_total - last_month_total) / last_month_total) * 100
    else:
        income_change_percent = 0 if current_month_total == 0 else 100
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Status counts
    paid_count = current_month_payments.filter(status='PAID').count()
    pending_count = current_month_payments.filter(status='PENDING').count()
    overdue_count = current_month_payments.filter(status='OVERDUE').count()
    partial_count = current_month_payments.filter(status='PARTIAL').count()
    
    context = {
        'current_month_payments': current_month_payments,
        'current_month_total': current_month_total,
        'current_month_pending': current_month_pending,
        'current_month_overdue': current_month_overdue,
        'last_month_total': last_month_total,
        'income_change_percent': income_change_percent,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'current_month_start': current_month_start,
        'current_month_end': current_month_end,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
        'partial_count': partial_count,
        'total_payments': current_month_payments.count(),
    }
    
    return render(request, 'dashboards/rent_income_detail.html', context)

@login_required
def monthly_expenses_detail(request):
    """Detailed view for monthly expenses metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get property filter from URL parameter
    property_id = request.GET.get('property')
    selected_property = None
    
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Date range calculations
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Base queries for expenses
    expense_records_query = ExpenseRecord.objects.filter(
        property__company=request.user.company
    ).select_related('property', 'apartment_unit', 'created_by')
    
    maintenance_invoices_query = MaintenanceInvoice.objects.filter(
        maintenance_request__property__company=request.user.company
    ).select_related(
        'maintenance_request__property',
        'maintenance_request__apartment_unit',
        'uploaded_by'
    )
    
    # Apply property filter
    if selected_property:
        expense_records_query = expense_records_query.filter(property=selected_property)
        maintenance_invoices_query = maintenance_invoices_query.filter(
            maintenance_request__property=selected_property
        )
    elif request.user.property:
        expense_records_query = expense_records_query.filter(property=request.user.property)
        maintenance_invoices_query = maintenance_invoices_query.filter(
            maintenance_request__property=request.user.property
        )
    
    # Current month data
    current_month_expense_records = expense_records_query.filter(
        expense_date__gte=current_month_start,
        expense_date__lte=current_month_end
    ).order_by('-expense_date')
    
    current_month_maintenance_invoices = maintenance_invoices_query.filter(
        invoice_date__gte=current_month_start,
        invoice_date__lte=current_month_end
    ).order_by('-invoice_date')
    
    # Calculate totals
    expense_records_total = current_month_expense_records.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    maintenance_invoices_total = current_month_maintenance_invoices.aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_expenses = expense_records_total + maintenance_invoices_total
    
    # Category breakdowns
    expense_categories = current_month_expense_records.values('category').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Counts
    total_expense_records = current_month_expense_records.count()
    total_maintenance_invoices = current_month_maintenance_invoices.count()
    total_entries = total_expense_records + total_maintenance_invoices
    
    context = {
        'current_month_expense_records': current_month_expense_records,
        'current_month_maintenance_invoices': current_month_maintenance_invoices,
        'expense_records_total': expense_records_total,
        'maintenance_invoices_total': maintenance_invoices_total,
        'total_expenses': total_expenses,
        'expense_categories': expense_categories,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'current_month_start': current_month_start,
        'current_month_end': current_month_end,
        'total_expense_records': total_expense_records,
        'total_maintenance_invoices': total_maintenance_invoices,
        'total_entries': total_entries,
    }
    
    return render(request, 'dashboards/monthly_expenses_detail.html', context)

@login_required
def monthly_revenue_detail(request):
    """Detailed view for monthly revenue metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get property filter from URL parameter
    property_id = request.GET.get('property')
    selected_property = None
    
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Get available properties for filter dropdown
    from properties.models import Property
    if request.user.role == User.Role.LANDLORD:
        available_properties = Property.objects.filter(company=request.user.company)
    else:  # Employee
        if request.user.property:
            available_properties = Property.objects.filter(id=request.user.property.id)
        else:
            available_properties = Property.objects.filter(company=request.user.company)
    
    # Date range calculations
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = current_month_start - timedelta(days=1)
    
    # Income calculations (rent payments)
    rent_payments_query = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company
    ).select_related(
        'payment_schedule__tenant',
        'payment_schedule__apartment_unit',
        'payment_schedule__apartment_unit__property'
    )
    
    # Apply property filter to rent payments
    if selected_property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=selected_property
        )
    elif request.user.property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    # Current month income
    current_month_income = rent_payments_query.filter(
        due_date__gte=current_month_start,
        due_date__lte=current_month_end,
        status='PAID'
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    # Last month income
    last_month_income = rent_payments_query.filter(
        due_date__gte=last_month_start,
        due_date__lte=last_month_end,
        status='PAID'
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    
    # Expense calculations
    expense_records_query = ExpenseRecord.objects.filter(
        property__company=request.user.company
    )
    
    maintenance_invoices_query = MaintenanceInvoice.objects.filter(
        maintenance_request__property__company=request.user.company
    )
    
    # Apply property filter to expenses
    if selected_property:
        expense_records_query = expense_records_query.filter(property=selected_property)
        maintenance_invoices_query = maintenance_invoices_query.filter(
            maintenance_request__property=selected_property
        )
    elif request.user.property:
        expense_records_query = expense_records_query.filter(property=request.user.property)
        maintenance_invoices_query = maintenance_invoices_query.filter(
            maintenance_request__property=request.user.property
        )
    
    # Current month expenses
    current_month_expense_records = expense_records_query.filter(
        expense_date__gte=current_month_start,
        expense_date__lte=current_month_end
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    current_month_maintenance_invoices = maintenance_invoices_query.filter(
        invoice_date__gte=current_month_start,
        invoice_date__lte=current_month_end
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    current_month_expenses = current_month_expense_records + current_month_maintenance_invoices
    
    # Last month expenses
    last_month_expense_records = expense_records_query.filter(
        expense_date__gte=last_month_start,
        expense_date__lte=last_month_end
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    last_month_maintenance_invoices = maintenance_invoices_query.filter(
        invoice_date__gte=last_month_start,
        invoice_date__lte=last_month_end
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    last_month_expenses = last_month_expense_records + last_month_maintenance_invoices
    
    # Revenue calculations
    current_month_revenue = current_month_income - current_month_expenses
    last_month_revenue = last_month_income - last_month_expenses
    
    # Revenue change percentage and amount
    revenue_change_amount = current_month_revenue - last_month_revenue
    revenue_change_percent = 0
    if last_month_revenue > 0:
        revenue_change_percent = ((current_month_revenue - last_month_revenue) / last_month_revenue) * 100
    elif current_month_revenue != 0:
        revenue_change_percent = 100 if current_month_revenue > 0 else -100
    
    # Get detailed data for breakdown
    current_month_paid_payments = rent_payments_query.filter(
        due_date__gte=current_month_start,
        due_date__lte=current_month_end,
        status='PAID'
    ).order_by('-payment_date')
    
    current_month_expense_list = ExpenseRecord.objects.filter(
        property__company=request.user.company,
        expense_date__gte=current_month_start,
        expense_date__lte=current_month_end
    ).select_related('property', 'apartment_unit', 'created_by').order_by('-expense_date')
    
    current_month_maintenance_list = MaintenanceInvoice.objects.filter(
        maintenance_request__property__company=request.user.company,
        invoice_date__gte=current_month_start,
        invoice_date__lte=current_month_end
    ).select_related(
        'maintenance_request__property',
        'maintenance_request__apartment_unit',
        'uploaded_by'
    ).order_by('-invoice_date')
    
    # Apply property filter to detailed lists
    if selected_property:
        current_month_expense_list = current_month_expense_list.filter(property=selected_property)
        current_month_maintenance_list = current_month_maintenance_list.filter(
            maintenance_request__property=selected_property
        )
    elif request.user.property:
        current_month_expense_list = current_month_expense_list.filter(property=request.user.property)
        current_month_maintenance_list = current_month_maintenance_list.filter(
            maintenance_request__property=request.user.property
        )
    
    context = {
        'current_month_income': current_month_income,
        'current_month_expenses': current_month_expenses,
        'current_month_revenue': current_month_revenue,
        'last_month_income': last_month_income,
        'last_month_expenses': last_month_expenses,
        'last_month_revenue': last_month_revenue,
        'revenue_change_percent': revenue_change_percent,
        'revenue_change_amount': revenue_change_amount,
        'current_month_expense_records': current_month_expense_records,
        'current_month_maintenance_invoices': current_month_maintenance_invoices,
        'current_month_paid_payments': current_month_paid_payments,
        'current_month_expense_list': current_month_expense_list,
        'current_month_maintenance_list': current_month_maintenance_list,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'current_month_start': current_month_start,
        'current_month_end': current_month_end,
        'total_income_entries': current_month_paid_payments.count(),
        'total_expense_entries': current_month_expense_list.count() + current_month_maintenance_list.count(),
    }
    
    return render(request, 'dashboards/monthly_revenue_detail.html', context)

@login_required
def maintenance_requests_detail(request):
    """Detailed view for maintenance requests metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Base query for maintenance requests
    maintenance_requests_query = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    ).select_related(
        'property',
        'apartment_unit',
        'tenant',
        'assigned_to',
        'category'
    ).prefetch_related('photos', 'invoices', 'updates')
    
    # Apply property filter
    if selected_property:
        maintenance_requests_query = maintenance_requests_query.filter(property=selected_property)
    elif request.user.property:
        maintenance_requests_query = maintenance_requests_query.filter(property=request.user.property)
    
    # Apply status filter
    if status_filter and status_filter != 'all':
        maintenance_requests_query = maintenance_requests_query.filter(status=status_filter)
    
    # Apply priority filter
    if priority_filter and priority_filter != 'all':
        maintenance_requests_query = maintenance_requests_query.filter(priority=priority_filter)
    
    # Apply search filter
    if search_query:
        maintenance_requests_query = maintenance_requests_query.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(tenant__username__icontains=search_query) |
            Q(apartment_unit__unit_number__icontains=search_query)
        )
    
    # Order by creation date (newest first)
    maintenance_requests = maintenance_requests_query.order_by('-created_at')
    
    # Calculate status counts for the filtered property
    base_count_query = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    )
    if selected_property:
        base_count_query = base_count_query.filter(property=selected_property)
    elif request.user.property:
        base_count_query = base_count_query.filter(property=request.user.property)
    
    status_counts = {
        'total': base_count_query.count(),
        'submitted': base_count_query.filter(status='SUBMITTED').count(),
        'in_progress': base_count_query.filter(status='IN_PROGRESS').count(),
        'scheduled': base_count_query.filter(status='SCHEDULED').count(),
        'completed': base_count_query.filter(status='COMPLETED').count(),
        'cancelled': base_count_query.filter(status='CANCELLED').count(),
    }
    
    # Calculate priority counts
    priority_counts = {
        'emergency': base_count_query.filter(priority='EMERGENCY').count(),
        'high': base_count_query.filter(priority='HIGH').count(),
        'medium': base_count_query.filter(priority='MEDIUM').count(),
        'low': base_count_query.filter(priority='LOW').count(),
    }
    
    # Recent activity (this month)
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_requests = base_count_query.filter(created_at__gte=current_month_start).count()
    completed_this_month = base_count_query.filter(
        status='COMPLETED',
        completed_at__gte=current_month_start
    ).count()
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Get maintenance categories for potential future filtering
    from maintenance.models import MaintenanceCategory
    categories = MaintenanceCategory.objects.all().order_by('name')
    
    context = {
        'maintenance_requests': maintenance_requests,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_query,
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'current_month_requests': current_month_requests,
        'completed_this_month': completed_this_month,
        'categories': categories,
        'filtered_count': maintenance_requests.count(),
        # Status choices for dropdowns
        'status_choices': MaintenanceRequest.Status.choices,
        'priority_choices': MaintenanceRequest.Priority.choices,
    }
    
    return render(request, 'dashboards/maintenance_requests_detail.html', context)

@login_required
def payment_status_detail(request):
    """Detailed view for payment status metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Date range calculations
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Base query for rent payments
    rent_payments_query = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company,
        due_date__gte=current_month_start,
        due_date__lte=current_month_end
    ).select_related(
        'payment_schedule__tenant',
        'payment_schedule__apartment_unit',
        'payment_schedule__apartment_unit__property'
    )
    
    # Apply property filter
    if selected_property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=selected_property
        )
    elif request.user.property:
        rent_payments_query = rent_payments_query.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    # Apply status filter
    if status_filter and status_filter != 'all':
        rent_payments_query = rent_payments_query.filter(status=status_filter)
    
    # Apply search filter
    if search_query:
        rent_payments_query = rent_payments_query.filter(
            Q(payment_schedule__tenant__first_name__icontains=search_query) |
            Q(payment_schedule__tenant__last_name__icontains=search_query) |
            Q(payment_schedule__tenant__username__icontains=search_query) |
            Q(payment_schedule__apartment_unit__unit_number__icontains=search_query) |
            Q(reference_number__icontains=search_query)
        )
    
    # Order by due date (most urgent first)
    rent_payments = rent_payments_query.order_by('due_date', 'payment_schedule__apartment_unit__unit_number')
    
    # Calculate status counts for the filtered property/company
    base_count_query = RentPayment.objects.filter(
        payment_schedule__apartment_unit__property__company=request.user.company,
        due_date__gte=current_month_start,
        due_date__lte=current_month_end
    )
    if selected_property:
        base_count_query = base_count_query.filter(
            payment_schedule__apartment_unit__property=selected_property
        )
    elif request.user.property:
        base_count_query = base_count_query.filter(
            payment_schedule__apartment_unit__property=request.user.property
        )
    
    status_counts = {
        'total': base_count_query.count(),
        'paid': base_count_query.filter(status='PAID').count(),
        'pending': base_count_query.filter(status='PENDING').count(),
        'overdue': base_count_query.filter(status='OVERDUE').count(),
        'partial': base_count_query.filter(status='PARTIAL').count(),
        'failed': base_count_query.filter(status='FAILED').count(),
    }
    
    # Calculate financial totals
    total_due = base_count_query.aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    total_paid = base_count_query.filter(status='PAID').aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
    total_outstanding = base_count_query.filter(status__in=['PENDING', 'OVERDUE', 'PARTIAL']).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    
    # Calculate collection rate
    if total_due > 0:
        collection_rate = round((total_paid / total_due) * 100)
    else:
        collection_rate = 0
    
    # On-time payment percentage
    if status_counts['total'] > 0:
        on_time_percentage = round((status_counts['paid'] / status_counts['total']) * 100)
    else:
        on_time_percentage = 0
    
    # Count unique tenants with late payments
    late_tenants_count = base_count_query.filter(
        status__in=['OVERDUE', 'PARTIAL']
    ).values('payment_schedule__tenant').distinct().count()
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    context = {
        'rent_payments': rent_payments,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_counts': status_counts,
        'total_due': total_due,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
        'collection_rate': collection_rate,
        'on_time_percentage': on_time_percentage,
        'late_tenants_count': late_tenants_count,
        'current_month_start': current_month_start,
        'current_month_end': current_month_end,
        'filtered_count': rent_payments.count(),
        # Status choices for dropdowns
        'status_choices': RentPayment.Status.choices,
    }
    
    return render(request, 'dashboards/payment_status_detail.html', context)

@login_required
def occupancy_rate_detail(request):
    """Detailed view for occupancy rate metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    status_filter = request.GET.get('status')  # 'occupied', 'vacant', or 'all'
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Base query for apartment units
    apartment_units_query = ApartmentUnit.objects.filter(
        property__company=request.user.company
    ).select_related(
        'property'
    ).prefetch_related(
        'tenant'  # Get tenants associated with this unit (reverse FK relationship)
    )
    
    # Apply property filter
    if selected_property:
        apartment_units_query = apartment_units_query.filter(property=selected_property)
    elif request.user.property:
        apartment_units_query = apartment_units_query.filter(property=request.user.property)
    
    # Apply status filter
    if status_filter == 'occupied':
        apartment_units_query = apartment_units_query.filter(tenant__isnull=False)
    elif status_filter == 'vacant':
        apartment_units_query = apartment_units_query.filter(tenant__isnull=True)
    # 'all' or None shows all units
    
    # Apply search filter
    if search_query:
        apartment_units_query = apartment_units_query.filter(
            Q(unit_number__icontains=search_query) |
            Q(property__name__icontains=search_query) |
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(tenant__username__icontains=search_query)
        ).distinct()
    
    # Order by property name and unit number
    apartment_units = apartment_units_query.order_by('property__name', 'unit_number')
    
    # Calculate occupancy statistics for the filtered scope
    base_count_query = ApartmentUnit.objects.filter(
        property__company=request.user.company
    )
    if selected_property:
        base_count_query = base_count_query.filter(property=selected_property)
    elif request.user.property:
        base_count_query = base_count_query.filter(property=request.user.property)
    
    total_units = base_count_query.count()
    occupied_units = base_count_query.filter(tenant__isnull=False).distinct().count()
    vacant_units = base_count_query.filter(tenant__isnull=True).count()
    
    # Calculate occupancy percentage
    if total_units > 0:
        occupancy_percentage = round((occupied_units / total_units) * 100)
    else:
        occupancy_percentage = 0
    
    # Calculate potential monthly income
    total_potential_income = base_count_query.aggregate(
        total=Sum('rent_amount')
    )['total'] or Decimal('0.00')
    
    occupied_income = base_count_query.filter(tenant__isnull=False).aggregate(
        total=Sum('rent_amount')
    )['total'] or Decimal('0.00')
    
    vacant_income_loss = total_potential_income - occupied_income
    
    # Get property breakdown for summary
    property_breakdown = base_count_query.values('property__name', 'property__id').annotate(
        total=Count('id'),
        occupied=Count('id', filter=Q(tenant__isnull=False)),
        vacant=Count('id', filter=Q(tenant__isnull=True)),
        potential_income=Sum('rent_amount'),
        occupied_income=Sum('rent_amount', filter=Q(tenant__isnull=False))
    ).order_by('property__name')
    
    # Add occupancy percentage to each property
    for prop in property_breakdown:
        if prop['total'] > 0:
            prop['occupancy_percentage'] = round((prop['occupied'] / prop['total']) * 100)
        else:
            prop['occupancy_percentage'] = 0
        prop['vacant_income_loss'] = (prop['potential_income'] or Decimal('0.00')) - (prop['occupied_income'] or Decimal('0.00'))
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Get recent vacancies (units that became vacant in the last 30 days)
    from django.utils import timezone
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_vacancies = base_count_query.filter(
        is_occupied=False,
        updated_at__gte=thirty_days_ago
    ).count()
    
    context = {
        'apartment_units': apartment_units,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_units': total_units,
        'occupied_units': occupied_units,
        'vacant_units': vacant_units,
        'occupancy_percentage': occupancy_percentage,
        'total_potential_income': total_potential_income,
        'occupied_income': occupied_income,
        'vacant_income_loss': vacant_income_loss,
        'property_breakdown': property_breakdown,
        'recent_vacancies': recent_vacancies,
        'filtered_count': apartment_units.count(),
        # Status choices for dropdown
        'status_choices': [
            ('all', 'All Units'),
            ('occupied', 'Occupied'),
            ('vacant', 'Vacant'),
        ],
    }
    
    return render(request, 'dashboards/occupancy_rate_detail.html', context)

@login_required
def lease_expirations_detail(request):
    """Detailed view for lease expirations metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    period_filter = request.GET.get('period', '90')  # 30, 60, 90, 180, 365 days
    status_filter = request.GET.get('status')  # 'active', 'expiring', 'expired', 'all'
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Date calculations
    from django.utils import timezone
    today = timezone.now().date()
    period_days = int(period_filter) if period_filter.isdigit() else 90
    future_date = today + timedelta(days=period_days)
    
    # Base query for payment schedules (which contain lease end dates)
    payment_schedules_query = PaymentSchedule.objects.filter(
        apartment_unit__property__company=request.user.company,
        is_active=True,
        end_date__isnull=False  # Only include schedules with lease end dates
    ).select_related(
        'tenant',
        'apartment_unit',
        'apartment_unit__property'
    ).order_by('end_date')
    
    # Apply property filter
    if selected_property:
        payment_schedules_query = payment_schedules_query.filter(
            apartment_unit__property=selected_property
        )
    elif request.user.property:
        payment_schedules_query = payment_schedules_query.filter(
            apartment_unit__property=request.user.property
        )
    
    # Apply status filter
    if status_filter == 'active':
        payment_schedules_query = payment_schedules_query.filter(end_date__gt=today)
    elif status_filter == 'expiring':
        payment_schedules_query = payment_schedules_query.filter(
            end_date__gte=today,
            end_date__lte=future_date
        )
    elif status_filter == 'expired':
        payment_schedules_query = payment_schedules_query.filter(end_date__lt=today)
    # 'all' shows all leases
    
    # Apply search filter
    if search_query:
        payment_schedules_query = payment_schedules_query.filter(
            Q(tenant__first_name__icontains=search_query) |
            Q(tenant__last_name__icontains=search_query) |
            Q(tenant__username__icontains=search_query) |
            Q(apartment_unit__unit_number__icontains=search_query) |
            Q(apartment_unit__property__name__icontains=search_query)
        )
    
    # Get all lease schedules
    all_payment_schedules = payment_schedules_query
    
    # Calculate lease statistics
    base_count_query = PaymentSchedule.objects.filter(
        apartment_unit__property__company=request.user.company,
        is_active=True,
        end_date__isnull=False
    )
    if selected_property:
        base_count_query = base_count_query.filter(apartment_unit__property=selected_property)
    elif request.user.property:
        base_count_query = base_count_query.filter(apartment_unit__property=request.user.property)
    
    total_leases = base_count_query.count()
    active_leases = base_count_query.filter(end_date__gt=today).count()
    expired_leases = base_count_query.filter(end_date__lt=today).count()
    
    # Time-based expiration counts
    expiring_30_days = base_count_query.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30)
    ).count()
    
    expiring_60_days = base_count_query.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=60)
    ).count()
    
    expiring_90_days = base_count_query.filter(
        end_date__gte=today,
        end_date__lte=today + timedelta(days=90)
    ).count()
    
    # Recent expirations (last 30 days)
    recent_expirations = base_count_query.filter(
        end_date__gte=today - timedelta(days=30),
        end_date__lt=today
    ).count()
    
    # Lease length analysis
    lease_length_analysis = []
    if total_leases > 0:
        # Calculate average lease length for completed leases
        completed_leases = base_count_query.exclude(end_date__isnull=True)
        for schedule in completed_leases:
            if schedule.start_date and schedule.end_date:
                length_days = (schedule.end_date - schedule.start_date).days
                lease_length_analysis.append(length_days)
    
    avg_lease_length_days = sum(lease_length_analysis) / len(lease_length_analysis) if lease_length_analysis else 0
    avg_lease_length_months = round(avg_lease_length_days / 30.44) if avg_lease_length_days > 0 else 0
    
    # Property breakdown (if showing all properties)
    property_breakdown = None
    if not selected_property:
        property_breakdown = base_count_query.values(
            'apartment_unit__property__name', 
            'apartment_unit__property__id'
        ).annotate(
            total_leases=Count('id'),
            active_leases=Count('id', filter=Q(end_date__gt=today)),
            expiring_30=Count('id', filter=Q(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=30)
            )),
            expiring_60=Count('id', filter=Q(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=60)
            )),
            expiring_90=Count('id', filter=Q(
                end_date__gte=today,
                end_date__lte=today + timedelta(days=90)
            )),
            expired_leases=Count('id', filter=Q(end_date__lt=today))
        ).order_by('apartment_unit__property__name')
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Add lease status and days until expiration to each schedule
    annotated_schedules = []
    for schedule in all_payment_schedules:
        days_until_expiration = (schedule.end_date - today).days if schedule.end_date else None
        days_since_expiration = None
        
        if schedule.end_date:
            if schedule.end_date < today:
                lease_status = 'expired'
                urgency = 'high'
                days_since_expiration = abs(days_until_expiration)
            elif days_until_expiration <= 30:
                lease_status = 'expiring_soon'
                urgency = 'high'
            elif days_until_expiration <= 60:
                lease_status = 'expiring_soon'
                urgency = 'medium'
            elif days_until_expiration <= 90:
                lease_status = 'expiring_later'
                urgency = 'low'
            else:
                lease_status = 'active'
                urgency = 'none'
        else:
            lease_status = 'no_end_date'
            urgency = 'none'
        
        annotated_schedules.append({
            'schedule': schedule,
            'days_until_expiration': days_until_expiration,
            'days_since_expiration': days_since_expiration,
            'lease_status': lease_status,
            'urgency': urgency
        })
    
    context = {
        'annotated_schedules': annotated_schedules,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'period_filter': period_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_leases': total_leases,
        'active_leases': active_leases,
        'expired_leases': expired_leases,
        'expiring_30_days': expiring_30_days,
        'expiring_60_days': expiring_60_days,
        'expiring_90_days': expiring_90_days,
        'recent_expirations': recent_expirations,
        'avg_lease_length_months': avg_lease_length_months,
        'property_breakdown': property_breakdown,
        'today': today,
        'future_date': future_date,
        'filtered_count': len(annotated_schedules),
        # Filter choices
        'period_choices': [
            ('30', '30 Days'),
            ('60', '60 Days'),
            ('90', '90 Days'),
            ('180', '6 Months'),
            ('365', '1 Year'),
        ],
        'status_choices': [
            ('all', 'All Leases'),
            ('active', 'Active'),
            ('expiring', f'Expiring within {period_days} days'),
            ('expired', 'Expired'),
        ],
    }
    
    return render(request, 'dashboards/lease_expirations_detail.html', context)

@login_required
def vacant_units_detail(request):
    """Detailed view for vacant units metrics"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    bedroom_filter = request.GET.get('bedrooms')  # Filter by number of bedrooms
    price_range = request.GET.get('price_range')  # 'low', 'medium', 'high'
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Base query for vacant apartment units
    vacant_units_query = ApartmentUnit.objects.filter(
        property__company=request.user.company,
        tenant__isnull=True  # No tenants assigned = vacant
    ).select_related(
        'property'
    ).order_by('property__name', 'unit_number')
    
    # Apply property filter
    if selected_property:
        vacant_units_query = vacant_units_query.filter(property=selected_property)
    elif request.user.property:
        vacant_units_query = vacant_units_query.filter(property=request.user.property)
    
    # Apply bedroom filter
    if bedroom_filter and bedroom_filter.isdigit():
        vacant_units_query = vacant_units_query.filter(bedrooms=int(bedroom_filter))
    
    # Apply price range filter
    if price_range:
        # Calculate price ranges based on all units
        all_rent_amounts = ApartmentUnit.objects.filter(
            property__company=request.user.company
        ).values_list('rent_amount', flat=True)
        
        if all_rent_amounts:
            rent_amounts = [amount for amount in all_rent_amounts if amount > 0]
            if rent_amounts:
                rent_amounts.sort()
                low_threshold = rent_amounts[len(rent_amounts)//3]
                high_threshold = rent_amounts[2*len(rent_amounts)//3]
                
                if price_range == 'low':
                    vacant_units_query = vacant_units_query.filter(rent_amount__lte=low_threshold)
                elif price_range == 'medium':
                    vacant_units_query = vacant_units_query.filter(
                        rent_amount__gt=low_threshold,
                        rent_amount__lte=high_threshold
                    )
                elif price_range == 'high':
                    vacant_units_query = vacant_units_query.filter(rent_amount__gt=high_threshold)
    
    # Apply search filter
    if search_query:
        vacant_units_query = vacant_units_query.filter(
            Q(unit_number__icontains=search_query) |
            Q(property__name__icontains=search_query)
        )
    
    # Get all vacant units
    vacant_units = vacant_units_query
    
    # Calculate vacancy statistics
    base_count_query = ApartmentUnit.objects.filter(
        property__company=request.user.company
    )
    if selected_property:
        base_count_query = base_count_query.filter(property=selected_property)
    elif request.user.property:
        base_count_query = base_count_query.filter(property=request.user.property)
    
    total_units = base_count_query.count()
    vacant_units_count = base_count_query.filter(tenant__isnull=True).count()
    occupied_units_count = base_count_query.filter(tenant__isnull=False).distinct().count()
    
    # Calculate vacancy percentage
    if total_units > 0:
        vacancy_percentage = round((vacant_units_count / total_units) * 100)
    else:
        vacancy_percentage = 0
    
    # Calculate potential income loss from vacant units
    total_potential_income = base_count_query.aggregate(
        total=Sum('rent_amount')
    )['total'] or Decimal('0.00')
    
    vacant_income_potential = base_count_query.filter(tenant__isnull=True).aggregate(
        total=Sum('rent_amount')
    )['total'] or Decimal('0.00')
    
    # Calculate recent vacancy changes (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recently_vacated = base_count_query.filter(
        tenant__isnull=True,
        updated_at__gte=thirty_days_ago
    ).count()
    
    # Bedroom breakdown for vacant units
    bedroom_breakdown = vacant_units_query.values('bedrooms').annotate(
        count=Count('id'),
        avg_rent=Avg('rent_amount'),
        total_potential=Sum('rent_amount')
    ).order_by('bedrooms')
    
    # Property breakdown (if showing all properties)
    property_breakdown = None
    if not selected_property:
        property_breakdown = base_count_query.values(
            'property__name', 
            'property__id'
        ).annotate(
            total_units=Count('id'),
            vacant_units=Count('id', filter=Q(tenant__isnull=True)),
            occupied_units=Count('id', filter=Q(tenant__isnull=False)),
            vacant_income_loss=Sum('rent_amount', filter=Q(tenant__isnull=True))
        ).order_by('property__name')
        
        # Add vacancy percentage to each property
        for prop in property_breakdown:
            if prop['total_units'] > 0:
                prop['vacancy_percentage'] = round((prop['vacant_units'] / prop['total_units']) * 100)
            else:
                prop['vacancy_percentage'] = 0
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Get unique bedroom counts for filter dropdown
    bedroom_options = ApartmentUnit.objects.filter(
        property__company=request.user.company
    ).values_list('bedrooms', flat=True).distinct().order_by('bedrooms')
    
    # Calculate average vacancy duration (this is an estimate based on last updated)
    # In a real system, you might track when units became vacant
    avg_vacancy_days = 0
    if vacant_units_count > 0:
        # Estimate based on how long ago units were last updated (rough approximation)
        vacancy_durations = []
        for unit in vacant_units_query:
            if unit.updated_at:
                days_vacant = (timezone.now() - unit.updated_at).days
                vacancy_durations.append(days_vacant)
        
        if vacancy_durations:
            avg_vacancy_days = sum(vacancy_durations) // len(vacancy_durations)
    
    # Add unit details with estimated vacancy duration
    annotated_units = []
    for unit in vacant_units:
        days_vacant = (timezone.now() - unit.updated_at).days if unit.updated_at else 0
        
        # Categorize vacancy duration
        if days_vacant <= 7:
            vacancy_status = 'new'
            urgency = 'low'
        elif days_vacant <= 30:
            vacancy_status = 'recent'
            urgency = 'medium'
        elif days_vacant <= 90:
            vacancy_status = 'extended'
            urgency = 'high'
        else:
            vacancy_status = 'long_term'
            urgency = 'critical'
        
        annotated_units.append({
            'unit': unit,
            'days_vacant': days_vacant,
            'vacancy_status': vacancy_status,
            'urgency': urgency
        })
    
    context = {
        'annotated_units': annotated_units,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'bedroom_filter': bedroom_filter,
        'price_range': price_range,
        'search_query': search_query,
        'total_units': total_units,
        'vacant_units_count': vacant_units_count,
        'occupied_units_count': occupied_units_count,
        'vacancy_percentage': vacancy_percentage,
        'total_potential_income': total_potential_income,
        'vacant_income_potential': vacant_income_potential,
        'recently_vacated': recently_vacated,
        'avg_vacancy_days': avg_vacancy_days,
        'bedroom_breakdown': bedroom_breakdown,
        'property_breakdown': property_breakdown,
        'bedroom_options': bedroom_options,
        'filtered_count': len(annotated_units),
        # Filter choices
        'bedroom_choices': [(str(br), f"{br} Bedroom{'s' if br != 1 else ''}") for br in bedroom_options],
        'price_range_choices': [
            ('all', 'All Price Ranges'),
            ('low', 'Low Price Range'),
            ('medium', 'Medium Price Range'),
            ('high', 'High Price Range'),
        ],
    }
    
    return render(request, 'dashboards/vacant_units_detail.html', context)

@login_required
def tenant_list(request):
    """Detailed view for tenant management"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords and employees to access this view
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    status_filter = request.GET.get('status')  # 'active', 'expiring_soon', 'all'
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Base query for tenants
    tenants_query = User.objects.filter(
        company=request.user.company,
        role=User.Role.TENANT
    ).select_related(
        'property',
        'apartment_unit',
        'apartment_unit__property'
    ).prefetch_related(
        'apartment_unit__payment_schedules'
    ).order_by('last_name', 'first_name', 'username')
    
    # Apply property filter
    if selected_property:
        tenants_query = tenants_query.filter(apartment_unit__property=selected_property)
    elif request.user.property:
        tenants_query = tenants_query.filter(apartment_unit__property=request.user.property)
    
    # Apply search filter
    if search_query:
        tenants_query = tenants_query.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(apartment_unit__unit_number__icontains=search_query)
        )
    
    # Get all tenants
    all_tenants = list(tenants_query)
    
    # Calculate lease expiration data and apply status filter
    today = timezone.now().date()
    
    # Annotate tenants with lease expiration information
    annotated_tenants = []
    for tenant in all_tenants:
        # Get active payment schedule (lease) for this tenant
        active_lease = None
        lease_status = 'no_lease'
        days_until_expiration = None
        lease_expiry_date = None
        
        # Try finding by tenant only first (more lenient approach)
        active_lease = PaymentSchedule.objects.filter(
            tenant=tenant,
            is_active=True,
            end_date__isnull=False
        ).first()
        
        if active_lease and active_lease.end_date:
            lease_expiry_date = active_lease.end_date
            days_until_expiration = (active_lease.end_date - today).days
            
            if active_lease.end_date < today:
                lease_status = 'expired'
            elif days_until_expiration <= 30:
                lease_status = 'expiring_soon'
            else:
                lease_status = 'active'
        
        # Apply status filter
        if status_filter and status_filter != 'all':
            if status_filter == 'active' and lease_status != 'active':
                continue
            elif status_filter == 'expiring_soon' and lease_status != 'expiring_soon':
                continue
            elif status_filter == 'expired' and lease_status != 'expired':
                continue
        
        annotated_tenants.append({
            'tenant': tenant,
            'active_lease': active_lease,
            'lease_status': lease_status,
            'days_until_expiration': days_until_expiration,
            'lease_expiry_date': lease_expiry_date,
        })
    
    # Calculate tenant statistics
    base_count_query = User.objects.filter(
        company=request.user.company,
        role=User.Role.TENANT
    )
    if selected_property:
        base_count_query = base_count_query.filter(apartment_unit__property=selected_property)
    elif request.user.property:
        base_count_query = base_count_query.filter(apartment_unit__property=request.user.property)
    
    total_tenants = base_count_query.count()
    tenants_with_units = base_count_query.filter(apartment_unit__isnull=False).count()
    tenants_without_units = base_count_query.filter(apartment_unit__isnull=True).count()
    
    # Lease status counts - need to count all tenant data, not just filtered results
    # Get all tenants for proper counting (before any status filtering)
    all_tenants_for_count = list(User.objects.filter(
        company=request.user.company,
        role=User.Role.TENANT
    ).select_related('apartment_unit', 'apartment_unit__property'))
    
    # Apply property filter for counting
    if selected_property:
        all_tenants_for_count = [t for t in all_tenants_for_count if t.apartment_unit and t.apartment_unit.property == selected_property]
    elif request.user.property:
        all_tenants_for_count = [t for t in all_tenants_for_count if t.apartment_unit and t.apartment_unit.property == request.user.property]
    
    leases_expiring_30_days = 0
    leases_expiring_90_days = 0
    active_leases = 0
    expired_leases = 0
    
    for tenant in all_tenants_for_count:
        # Use the same lenient approach for counting
        active_lease = PaymentSchedule.objects.filter(
            tenant=tenant,
            is_active=True,
            end_date__isnull=False
        ).first()
        
        if active_lease and active_lease.end_date:
                days_until_expiration = (active_lease.end_date - today).days
                
                if active_lease.end_date < today:
                    expired_leases += 1
                elif days_until_expiration <= 30:
                    leases_expiring_30_days += 1
                    active_leases += 1  # Expiring soon is still active
                else:
                    active_leases += 1
                
                # Count towards 90-day expiration if within 90 days
                if days_until_expiration <= 90 and active_lease.end_date >= today:
                    leases_expiring_90_days += 1
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    if request.user.property:
        available_properties = available_properties.filter(id=request.user.property.id)
    
    # Property breakdown (if showing all properties)
    property_breakdown = None
    if not selected_property and request.user.role == User.Role.LANDLORD:
        property_breakdown = available_properties.annotate(
            tenant_count=Count('units__tenant', filter=Q(units__tenant__role=User.Role.TENANT))
        ).order_by('name')
    
    context = {
        'annotated_tenants': annotated_tenants,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_tenants': total_tenants,
        'tenants_with_units': tenants_with_units,
        'tenants_without_units': tenants_without_units,
        'leases_expiring_30_days': leases_expiring_30_days,
        'leases_expiring_90_days': leases_expiring_90_days,
        'active_leases': active_leases,
        'expired_leases': expired_leases,
        'property_breakdown': property_breakdown,
        'today': today,
        'filtered_count': len(annotated_tenants),
        # Filter choices
        'status_choices': [
            ('all', 'All Tenants'),
            ('active', 'Active Leases'),
            ('expiring_soon', 'Expiring Soon (≤30 days)'),
            ('expired', 'Expired Leases'),
        ],
    }
    
    return render(request, 'dashboards/tenant_list.html', context)

@login_required
def tenant_rent_status_detail(request):
    """Detailed view for tenant rent status and payment history"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow tenants to access this view
    if request.user.role != User.Role.TENANT:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    status_filter = request.GET.get('status', 'all')  # 'all', 'pending', 'paid', 'overdue'
    period_filter = request.GET.get('period', '12')  # months to show
    
    # Date calculations
    today = timezone.now().date()
    period_months = int(period_filter) if period_filter.isdigit() else 12
    start_date = today - timedelta(days=period_months * 30)  # Approximate months to days
    
    # Get tenant's payment schedule (current lease info)
    current_schedule = PaymentSchedule.objects.filter(
        tenant=request.user,
        is_active=True
    ).select_related('apartment_unit', 'apartment_unit__property').first()
    
    # Get tenant's payment history
    payments_query = RentPayment.objects.filter(
        payment_schedule__tenant=request.user
    ).select_related('payment_schedule', 'payment_schedule__apartment_unit')
    
    # Apply date filter
    payments_query = payments_query.filter(due_date__gte=start_date)
    
    # Apply status filter
    if status_filter != 'all':
        payments_query = payments_query.filter(status=status_filter.upper())
    
    # Order by due date (most recent first)
    payments = payments_query.order_by('-due_date')
    
    # Calculate payment statistics
    all_payments = RentPayment.objects.filter(
        payment_schedule__tenant=request.user,
        due_date__gte=start_date
    )
    
    total_payments = all_payments.count()
    paid_payments = all_payments.filter(status='PAID').count()
    pending_payments = all_payments.filter(status='PENDING').count()
    overdue_payments = all_payments.filter(status='OVERDUE').count()
    partial_payments = all_payments.filter(status='PARTIAL').count()
    failed_payments = all_payments.filter(status='FAILED').count()
    
    # Calculate totals
    total_amount_due = all_payments.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
    total_amount_paid = all_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
    outstanding_balance = total_amount_due - total_amount_paid
    
    # Calculate payment performance percentage
    payment_rate = 0
    if total_payments > 0:
        payment_rate = round((paid_payments / total_payments) * 100)
    
    # Get next upcoming payment
    next_payment = RentPayment.objects.filter(
        payment_schedule__tenant=request.user,
        status__in=['PENDING'],
        due_date__gte=today
    ).order_by('due_date').first()
    
    # If no next payment exists but we have a schedule, calculate the next due date
    calculated_next_payment = None
    if not next_payment and current_schedule:
        
        # Calculate next payment due date based on schedule
        if current_schedule.frequency == 'MONTHLY':
            # Find next month's payment date
            year = today.year
            month = today.month
            day = current_schedule.payment_day
            
            # If this month's payment day hasn't passed, use this month
            if today.day <= day:
                calculated_due_date = date(year, month, day)
            else:
                # Move to next month
                if month == 12:
                    year += 1
                    month = 1
                else:
                    month += 1
                calculated_due_date = date(year, month, day)
            
            # Create a simulated payment object for display
            calculated_next_payment = {
                'due_date': calculated_due_date,
                'amount_due': current_schedule.rent_amount,
                'status': 'PENDING'
            }
    
    # Calculate lease information
    lease_status = 'no_lease'
    days_until_lease_end = None
    lease_end_date = None
    
    if current_schedule and current_schedule.end_date:
        lease_end_date = current_schedule.end_date
        days_until_lease_end = (current_schedule.end_date - today).days
        
        if current_schedule.end_date < today:
            lease_status = 'expired'
        elif days_until_lease_end <= 30:
            lease_status = 'expiring_soon'
        else:
            lease_status = 'active'
    
    # Payment method breakdown (last 12 months)
    payment_method_breakdown = all_payments.values('payment_method').annotate(
        count=Count('id'),
        total_amount=Sum('amount_paid')
    ).order_by('-count')
    
    # Monthly payment trend (last 12 months)
    monthly_trends = []
    for i in range(12):
        month_start = today.replace(day=1) - timedelta(days=i*30)
        month_end = month_start + timedelta(days=31)
        
        month_payments = all_payments.filter(
            due_date__gte=month_start,
            due_date__lt=month_end
        )
        
        month_total = month_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        month_due = month_payments.aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')
        
        monthly_trends.append({
            'month': month_start.strftime('%b %Y'),
            'amount_paid': month_total,
            'amount_due': month_due,
            'payment_count': month_payments.count()
        })
    
    monthly_trends.reverse()  # Show oldest to newest
    
    # Recent payment activity (last 5 transactions)
    recent_payments = all_payments.order_by('-updated_at')[:5]
    
    # Add payment status information to each payment
    annotated_payments = []
    for payment in payments:
        days_overdue = 0
        urgency = 'none'
        
        if payment.status == 'OVERDUE' and payment.due_date:
            days_overdue = (today - payment.due_date).days
            if days_overdue > 30:
                urgency = 'high'
            elif days_overdue > 7:
                urgency = 'medium'
            else:
                urgency = 'low'
        elif payment.status == 'PENDING' and payment.due_date:
            days_until_due = (payment.due_date - today).days
            if days_until_due <= 3:
                urgency = 'medium'
            elif days_until_due <= 7:
                urgency = 'low'
        
        annotated_payments.append({
            'payment': payment,
            'days_overdue': days_overdue,
            'urgency': urgency
        })
    
    context = {
        'current_schedule': current_schedule,
        'annotated_payments': annotated_payments,
        'recent_payments': recent_payments,
        'next_payment': next_payment,
        'calculated_next_payment': calculated_next_payment,
        'status_filter': status_filter,
        'period_filter': period_filter,
        # Payment statistics
        'total_payments': total_payments,
        'paid_payments': paid_payments,
        'pending_payments': pending_payments,
        'overdue_payments': overdue_payments,
        'partial_payments': partial_payments,
        'failed_payments': failed_payments,
        'payment_rate': payment_rate,
        # Financial totals
        'total_amount_due': total_amount_due,
        'total_amount_paid': total_amount_paid,
        'outstanding_balance': outstanding_balance,
        # Lease information
        'lease_status': lease_status,
        'days_until_lease_end': days_until_lease_end,
        'lease_end_date': lease_end_date,
        # Trends and breakdowns
        'payment_method_breakdown': payment_method_breakdown,
        'monthly_trends': monthly_trends,
        'today': today,
        'filtered_count': len(annotated_payments),
        # Filter choices
        'status_choices': [
            ('all', 'All Payments'),
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('partial', 'Partial'),
            ('failed', 'Failed'),
        ],
        'period_choices': [
            ('3', 'Last 3 Months'),
            ('6', 'Last 6 Months'),
            ('12', 'Last 12 Months'),
            ('24', 'Last 24 Months'),
        ],
    }
    
    return render(request, 'dashboards/tenant_rent_status_detail.html', context)

@login_required
def tenant_lease_end_detail(request):
    """Detailed view for tenant lease information and renewal options"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow tenants to access this view
    if request.user.role != User.Role.TENANT:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get tenant's current payment schedule (lease information)
    current_schedule = PaymentSchedule.objects.filter(
        tenant=request.user,
        is_active=True
    ).select_related('apartment_unit', 'apartment_unit__property').first()
    
    # Calculate lease information
    today = timezone.now().date()
    lease_status = 'no_lease'
    days_until_lease_end = None
    days_since_lease_end = None
    lease_end_date = None
    lease_length_days = None
    lease_length_months = None
    
    if current_schedule:
        if current_schedule.end_date:
            lease_end_date = current_schedule.end_date
            days_until_lease_end = (current_schedule.end_date - today).days
            
            if current_schedule.end_date < today:
                lease_status = 'expired'
                days_since_lease_end = abs(days_until_lease_end)
                days_until_lease_end = None  # Clear this for expired leases
            elif days_until_lease_end <= 30:
                lease_status = 'expiring_soon'
            elif days_until_lease_end <= 90:
                lease_status = 'expiring_later'
            else:
                lease_status = 'active'
            
            # Calculate lease length
            if current_schedule.start_date:
                lease_length_days = (current_schedule.end_date - current_schedule.start_date).days
                lease_length_months = round(lease_length_days / 30.44)  # Average days per month
        else:
            lease_status = 'month_to_month'
    
    # Get lease history (previous payment schedules for this tenant)
    lease_history = PaymentSchedule.objects.filter(
        tenant=request.user,
        is_active=False
    ).select_related('apartment_unit', 'apartment_unit__property').order_by('-end_date')
    
    # Calculate renewal timeline
    renewal_milestones = []
    if current_schedule and current_schedule.end_date and lease_status in ['active', 'expiring_later', 'expiring_soon']:
        # 90 days before expiration - Initial renewal notice
        notice_90_days = current_schedule.end_date - timedelta(days=90)
        renewal_milestones.append({
            'date': notice_90_days,
            'title': 'Renewal Notice Period',
            'description': 'Typical time to receive lease renewal notice',
            'status': 'completed' if today >= notice_90_days else 'upcoming',
            'urgency': 'low'
        })
        
        # 60 days before expiration - Renewal decision time
        decision_60_days = current_schedule.end_date - timedelta(days=60)
        renewal_milestones.append({
            'date': decision_60_days,
            'title': 'Decision Deadline Approaching',
            'description': 'Time to make renewal decision',
            'status': 'completed' if today >= decision_60_days else 'upcoming',
            'urgency': 'medium'
        })
        
        # 30 days before expiration - Final notice
        final_30_days = current_schedule.end_date - timedelta(days=30)
        renewal_milestones.append({
            'date': final_30_days,
            'title': 'Final Notice Period',
            'description': 'Last chance to finalize renewal or moving plans',
            'status': 'completed' if today >= final_30_days else 'upcoming',
            'urgency': 'high'
        })
        
        # Lease end date
        renewal_milestones.append({
            'date': current_schedule.end_date,
            'title': 'Lease Expires',
            'description': 'Current lease agreement ends',
            'status': 'completed' if today >= current_schedule.end_date else 'upcoming',
            'urgency': 'critical'
        })
    
    # Calculate important dates and statistics
    lease_stats = {
        'total_lease_periods': PaymentSchedule.objects.filter(tenant=request.user).count(),
        'current_property_tenure': None,
        'average_lease_length': None,
        'longest_lease': None,
    }
    
    # Calculate current property tenure
    if current_schedule and current_schedule.start_date:
        lease_stats['current_property_tenure'] = (today - current_schedule.start_date).days
    
    # Calculate average lease length from completed leases
    completed_leases = PaymentSchedule.objects.filter(
        tenant=request.user,
        start_date__isnull=False,
        end_date__isnull=False
    )
    
    if completed_leases.exists():
        lease_lengths = []
        longest_lease_days = 0
        
        for lease in completed_leases:
            length = (lease.end_date - lease.start_date).days
            lease_lengths.append(length)
            if length > longest_lease_days:
                longest_lease_days = length
        
        if lease_lengths:
            lease_stats['average_lease_length'] = round(sum(lease_lengths) / len(lease_lengths))
            lease_stats['longest_lease'] = longest_lease_days
    
    # Get related information
    # Recent maintenance requests for this tenant
    recent_maintenance = MaintenanceRequest.objects.filter(
        tenant=request.user
    ).order_by('-created_at')[:5]
    
    # Recent payments
    recent_payments = RentPayment.objects.filter(
        payment_schedule__tenant=request.user
    ).order_by('-due_date')[:5]
    
    context = {
        'current_schedule': current_schedule,
        'lease_status': lease_status,
        'days_until_lease_end': days_until_lease_end,
        'days_since_lease_end': days_since_lease_end,
        'lease_end_date': lease_end_date,
        'lease_length_days': lease_length_days,
        'lease_length_months': lease_length_months,
        'lease_history': lease_history,
        'renewal_milestones': renewal_milestones,
        'lease_stats': lease_stats,
        'recent_maintenance': recent_maintenance,
        'recent_payments': recent_payments,
        'today': today,
    }
    
    return render(request, 'dashboards/tenant_lease_end_detail.html', context)


@login_required
def tenant_maintenance_requests_detail(request):
    """Expanded view for tenant maintenance requests"""
    
    # Ensure user is a tenant
    if request.user.role != User.Role.TENANT:
        return redirect('core:dashboard_redirect')
    
    # Get user's maintenance requests
    tenant_maintenance_requests = MaintenanceRequest.objects.filter(
        tenant=request.user
    ).select_related(
        'category', 'property', 'apartment_unit', 'assigned_to'
    ).prefetch_related('photos')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        tenant_maintenance_requests = tenant_maintenance_requests.filter(status=status_filter)
    
    # Filter by priority if provided
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tenant_maintenance_requests = tenant_maintenance_requests.filter(priority=priority_filter)
    
    # Filter by date range
    date_filter = request.GET.get('date_range', '')
    if date_filter == 'last_week':
        week_ago = timezone.now() - timedelta(days=7)
        tenant_maintenance_requests = tenant_maintenance_requests.filter(created_at__gte=week_ago)
    elif date_filter == 'last_month':
        month_ago = timezone.now() - timedelta(days=30)
        tenant_maintenance_requests = tenant_maintenance_requests.filter(created_at__gte=month_ago)
    elif date_filter == 'last_year':
        year_ago = timezone.now() - timedelta(days=365)
        tenant_maintenance_requests = tenant_maintenance_requests.filter(created_at__gte=year_ago)
    
    # Calculate statistics
    total_requests = tenant_maintenance_requests.count()
    open_requests = tenant_maintenance_requests.exclude(status='COMPLETED').count()
    in_progress_requests = tenant_maintenance_requests.filter(status='IN_PROGRESS').count()
    scheduled_requests = tenant_maintenance_requests.filter(status='SCHEDULED').count()
    completed_requests = tenant_maintenance_requests.filter(status='COMPLETED').count()
    emergency_requests = tenant_maintenance_requests.filter(priority='EMERGENCY').count()
    
    # Status breakdown for charts
    status_breakdown = {
        'submitted': tenant_maintenance_requests.filter(status='SUBMITTED').count(),
        'in_progress': in_progress_requests,
        'scheduled': scheduled_requests,
        'completed': completed_requests,
        'cancelled': tenant_maintenance_requests.filter(status='CANCELLED').count(),
    }
    
    # Priority breakdown
    priority_breakdown = {
        'emergency': emergency_requests,
        'high': tenant_maintenance_requests.filter(priority='HIGH').count(),
        'medium': tenant_maintenance_requests.filter(priority='MEDIUM').count(),
        'low': tenant_maintenance_requests.filter(priority='LOW').count(),
    }
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_activity = tenant_maintenance_requests.filter(
        updated_at__gte=thirty_days_ago
    ).order_by('-updated_at')[:10]
    
    # Average response time calculation
    completed_with_times = tenant_maintenance_requests.filter(
        status='COMPLETED',
        completed_at__isnull=False
    )
    
    avg_response_time_days = None
    if completed_with_times.exists():
        total_time = sum([
            (req.completed_at - req.created_at).days 
            for req in completed_with_times 
            if req.completed_at and req.created_at
        ])
        avg_response_time_days = total_time / completed_with_times.count() if completed_with_times.count() > 0 else 0
    
    # Monthly request trend (last 6 months)
    monthly_trends = []
    for i in range(6):
        month_start = (timezone.now().replace(day=1) - timedelta(days=i*30)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_requests = tenant_maintenance_requests.filter(
            created_at__gte=month_start,
            created_at__lt=next_month
        ).count()
        
        monthly_trends.append({
            'month': month_start.strftime('%b %Y'),
            'count': month_requests
        })
    
    monthly_trends.reverse()  # Show oldest to newest
    
    # Categories breakdown
    categories = MaintenanceCategory.objects.all()
    category_stats = []
    for category in categories:
        count = tenant_maintenance_requests.filter(category=category).count()
        if count > 0:
            category_stats.append({
                'name': category.name,
                'count': count,
                'is_emergency': category.is_emergency
            })
    
    # Order requests by creation date (newest first)
    tenant_maintenance_requests = tenant_maintenance_requests.order_by('-created_at')
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(tenant_maintenance_requests, 10)  # 10 requests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'maintenance_requests': page_obj,
        'total_requests': total_requests,
        'open_requests': open_requests,
        'in_progress_requests': in_progress_requests,
        'scheduled_requests': scheduled_requests,
        'completed_requests': completed_requests,
        'emergency_requests': emergency_requests,
        'status_breakdown': status_breakdown,
        'priority_breakdown': priority_breakdown,
        'recent_activity': recent_activity,
        'avg_response_time_days': avg_response_time_days,
        'monthly_trends': monthly_trends,
        'category_stats': category_stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'date_filter': date_filter,
        'status_choices': MaintenanceRequest.Status.choices,
        'priority_choices': MaintenanceRequest.Priority.choices,
    }
    
    return render(request, 'dashboards/tenant_maintenance_requests_detail.html', context)


@login_required
def tenant_messages_detail(request):
    """Expanded view for tenant messages and communications"""
    
    # Ensure user is a tenant
    if request.user.role != User.Role.TENANT:
        return redirect('core:dashboard_redirect')
    
    # Get user's message threads
    message_threads = MessageThread.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages__sender', 'messages__messagereadstatus_set').order_by('-updated_at')
    
    # Filter by read status if provided
    read_filter = request.GET.get('read_status', '')
    if read_filter == 'unread':
        # Filter threads that have unread messages for the current user
        unread_thread_ids = []
        for thread in message_threads:
            unread_messages = thread.messages.exclude(
                messagereadstatus__user=request.user
            ).exclude(sender=request.user)
            if unread_messages.exists():
                unread_thread_ids.append(thread.id)
        message_threads = message_threads.filter(id__in=unread_thread_ids)
    elif read_filter == 'read':
        # Filter threads where all messages are read
        read_thread_ids = []
        for thread in message_threads:
            unread_messages = thread.messages.exclude(
                messagereadstatus__user=request.user
            ).exclude(sender=request.user)
            if not unread_messages.exists():
                read_thread_ids.append(thread.id)
        message_threads = message_threads.filter(id__in=read_thread_ids)
    
    # Filter by date range
    date_filter = request.GET.get('date_range', '')
    if date_filter == 'last_week':
        week_ago = timezone.now() - timedelta(days=7)
        message_threads = message_threads.filter(updated_at__gte=week_ago)
    elif date_filter == 'last_month':
        month_ago = timezone.now() - timedelta(days=30)
        message_threads = message_threads.filter(updated_at__gte=month_ago)
    elif date_filter == 'last_year':
        year_ago = timezone.now() - timedelta(days=365)
        message_threads = message_threads.filter(updated_at__gte=year_ago)
    
    # Calculate statistics
    all_threads = MessageThread.objects.filter(participants=request.user)
    total_threads = all_threads.count()
    
    # Count unread threads
    unread_threads_count = 0
    read_threads_count = 0
    for thread in all_threads:
        unread_messages = thread.messages.exclude(
            messagereadstatus__user=request.user
        ).exclude(sender=request.user)
        if unread_messages.exists():
            unread_threads_count += 1
        else:
            read_threads_count += 1
    
    # Get total message counts
    all_messages = Message.objects.filter(thread__participants=request.user)
    total_messages = all_messages.count()
    sent_messages = all_messages.filter(sender=request.user).count()
    received_messages = total_messages - sent_messages
    
    # Count unread messages
    unread_messages_count = 0
    for thread in all_threads:
        unread_messages = thread.messages.exclude(
            messagereadstatus__user=request.user
        ).exclude(sender=request.user)
        unread_messages_count += unread_messages.count()
    
    # Recent activity (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_messages = Message.objects.filter(
        thread__participants=request.user,
        created_at__gte=thirty_days_ago
    ).order_by('-created_at')[:10]
    
    # Monthly message trend (last 6 months)
    monthly_trends = []
    for i in range(6):
        month_start = (timezone.now().replace(day=1) - timedelta(days=i*30)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        
        month_messages = Message.objects.filter(
            thread__participants=request.user,
            created_at__gte=month_start,
            created_at__lt=next_month
        ).count()
        
        monthly_trends.append({
            'month': month_start.strftime('%b %Y'),
            'count': month_messages
        })
    
    monthly_trends.reverse()  # Show oldest to newest
    
    # Get user's notifications
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]
    
    # Calculate response times for conversations
    response_times = []
    for thread in all_threads[:20]:  # Sample recent threads
        thread_messages = thread.messages.order_by('created_at')
        if thread_messages.count() >= 2:
            for i in range(1, min(thread_messages.count(), 10)):  # Sample first 10 exchanges
                current_msg = thread_messages[i]
                previous_msg = thread_messages[i-1]
                if current_msg.sender != previous_msg.sender:  # Different senders
                    time_diff = (current_msg.created_at - previous_msg.created_at).total_seconds() / 3600  # hours
                    if time_diff < 168:  # Less than a week
                        response_times.append(time_diff)
    
    avg_response_time_hours = sum(response_times) / len(response_times) if response_times else None
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(message_threads, 10)  # 10 threads per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # For each thread in the current page, calculate unread count and get participants
    for thread in page_obj:
        # Calculate unread count for this thread
        unread_messages = thread.messages.exclude(
            messagereadstatus__user=request.user
        ).exclude(sender=request.user)
        thread.unread_count = unread_messages.count()
        
        # Get other participants (exclude current user)
        thread.other_participants = thread.participants.exclude(id=request.user.id)
    
    context = {
        'message_threads': page_obj,
        'total_threads': total_threads,
        'unread_threads_count': unread_threads_count,
        'read_threads_count': read_threads_count,
        'total_messages': total_messages,
        'sent_messages': sent_messages,
        'received_messages': received_messages,
        'unread_messages_count': unread_messages_count,
        'recent_messages': recent_messages,
        'monthly_trends': monthly_trends,
        'notifications': notifications,
        'avg_response_time_hours': avg_response_time_hours,
        'read_filter': read_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'dashboards/tenant_messages_detail.html', context)

@login_required
def employee_assigned_tasks_detail(request):
    """Expanded view for employee assigned maintenance tasks"""
    
    # Ensure user is an employee
    if request.user.role != User.Role.EMPLOYEE:
        return redirect('core:dashboard_redirect')
    
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Get all maintenance requests for the company
    maintenance_requests = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    ).select_related('property', 'apartment_unit', 'assigned_to', 'tenant', 'category')
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        maintenance_requests = maintenance_requests.filter(property=request.user.property)
    
    # Base queryset for assigned tasks (only tasks assigned to current employee)
    assigned_tasks = maintenance_requests.filter(assigned_to=request.user)
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('search', '')
    
    if status_filter:
        assigned_tasks = assigned_tasks.filter(status=status_filter)
    
    if priority_filter:
        assigned_tasks = assigned_tasks.filter(priority=priority_filter)
    
    if category_filter:
        assigned_tasks = assigned_tasks.filter(category_id=category_filter)
    
    if search:
        assigned_tasks = assigned_tasks.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(apartment_unit__unit_number__icontains=search) |
            Q(tenant__first_name__icontains=search) |
            Q(tenant__last_name__icontains=search)
        )
    
    # Order by priority and created date
    assigned_tasks = assigned_tasks.order_by(
        '-priority',  # Emergency first, then High, Medium, Low
        '-created_at'
    )
    
    # Calculate summary statistics
    total_assigned = assigned_tasks.count()
    
    # Status breakdown
    status_counts = {
        'SUBMITTED': assigned_tasks.filter(status='SUBMITTED').count(),
        'IN_PROGRESS': assigned_tasks.filter(status='IN_PROGRESS').count(),
        'SCHEDULED': assigned_tasks.filter(status='SCHEDULED').count(),
        'COMPLETED': assigned_tasks.filter(status='COMPLETED').count(),
    }
    
    # Priority breakdown
    priority_counts = {
        'EMERGENCY': assigned_tasks.filter(priority='EMERGENCY').count(),
        'HIGH': assigned_tasks.filter(priority='HIGH').count(),
        'MEDIUM': assigned_tasks.filter(priority='MEDIUM').count(),
        'LOW': assigned_tasks.filter(priority='LOW').count(),
    }
    
    # Active tasks (not completed)
    active_tasks = assigned_tasks.exclude(status='COMPLETED').count()
    
    # Overdue tasks (scheduled in the past but not completed)
    overdue_tasks = assigned_tasks.filter(
        scheduled_date__lt=timezone.now(),
        status__in=['SUBMITTED', 'IN_PROGRESS', 'SCHEDULED']
    ).count()
    
    # Upcoming scheduled tasks (within next 7 days)
    upcoming_tasks = assigned_tasks.filter(
        scheduled_date__gte=timezone.now(),
        scheduled_date__lte=timezone.now() + timedelta(days=7),
        status='SCHEDULED'
    ).count()
    
    # Recent completions (last 30 days)
    recent_completions = assigned_tasks.filter(
        status='COMPLETED',
        updated_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Get available categories for filter dropdown
    categories = MaintenanceCategory.objects.all()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(assigned_tasks, 10)  # Show 10 tasks per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'assigned_tasks': page_obj,
        'total_assigned': total_assigned,
        'active_tasks': active_tasks,
        'overdue_tasks': overdue_tasks,
        'upcoming_tasks': upcoming_tasks,
        'recent_completions': recent_completions,
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'categories': categories,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'search': search,
        'user_property': request.user.property,
    }
    
    return render(request, 'dashboards/employee_assigned_tasks_detail.html', context)

@login_required
def employee_todays_schedule_detail(request):
    """Expanded view for employee today's schedule"""
    
    # Ensure user is an employee
    if request.user.role != User.Role.EMPLOYEE:
        return redirect('core:dashboard_redirect')
    
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Get date filter (default to today)
    date_filter = request.GET.get('date', '')
    if date_filter:
        try:
            target_date = timezone.datetime.strptime(date_filter, '%Y-%m-%d').date()
        except ValueError:
            target_date = timezone.localtime().date()
    else:
        target_date = timezone.localtime().date()
    
    # Define date range for the target date
    date_start = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.min.time()))
    date_end = timezone.make_aware(timezone.datetime.combine(target_date, timezone.datetime.max.time()))
    
    # Get calendar events for the target date
    events_query = CalendarEvent.objects.filter(
        assigned_to=request.user,
        start_datetime__gte=date_start,
        start_datetime__lte=date_end,
        is_cancelled=False
    ).select_related('property', 'apartment_unit', 'maintenance_request', 'created_by')
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        events_query = events_query.filter(property=request.user.property)
    
    # Apply filters
    event_type_filter = request.GET.get('event_type', '')
    priority_filter = request.GET.get('priority', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    if event_type_filter:
        events_query = events_query.filter(event_type=event_type_filter)
    
    if priority_filter:
        events_query = events_query.filter(priority=priority_filter)
    
    if status_filter == 'completed':
        events_query = events_query.filter(is_completed=True)
    elif status_filter == 'pending':
        events_query = events_query.filter(is_completed=False)
    
    if search:
        events_query = events_query.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(location_details__icontains=search) |
            Q(apartment_unit__unit_number__icontains=search)
        )
    
    # Order by start time
    events = events_query.order_by('start_datetime')
    
    # Calculate summary statistics
    total_events = events.count()
    completed_events = events.filter(is_completed=True).count()
    pending_events = events.filter(is_completed=False).count()
    
    # Event type breakdown
    event_type_counts = {
        'MAINTENANCE': events.filter(event_type='MAINTENANCE').count(),
        'MEETING': events.filter(event_type='MEETING').count(),
        'INSPECTION': events.filter(event_type='INSPECTION').count(),
        'WORK_SCHEDULE': events.filter(event_type='WORK_SCHEDULE').count(),
        'GENERAL': events.filter(event_type='GENERAL').count(),
    }
    
    # Priority breakdown
    priority_counts = {
        'URGENT': events.filter(priority='URGENT').count(),
        'HIGH': events.filter(priority='HIGH').count(),
        'MEDIUM': events.filter(priority='MEDIUM').count(),
        'LOW': events.filter(priority='LOW').count(),
    }
    
    # Time-based statistics
    morning_events = events.filter(start_datetime__hour__lt=12).count()  # Before noon
    afternoon_events = events.filter(start_datetime__hour__gte=12, start_datetime__hour__lt=17).count()  # 12-5 PM
    evening_events = events.filter(start_datetime__hour__gte=17).count()  # After 5 PM
    
    # Upcoming events (next 7 days) for context
    next_week_start = timezone.now()
    next_week_end = timezone.now() + timedelta(days=7)
    upcoming_events_count = CalendarEvent.objects.filter(
        assigned_to=request.user,
        start_datetime__gte=next_week_start,
        start_datetime__lte=next_week_end,
        is_cancelled=False
    ).count()
    
    # Previous/Next day navigation
    previous_day = target_date - timedelta(days=1)
    next_day = target_date + timedelta(days=1)
    
    context = {
        'events': events,
        'target_date': target_date,
        'total_events': total_events,
        'completed_events': completed_events,
        'pending_events': pending_events,
        'event_type_counts': event_type_counts,
        'priority_counts': priority_counts,
        'morning_events': morning_events,
        'afternoon_events': afternoon_events,
        'evening_events': evening_events,
        'upcoming_events_count': upcoming_events_count,
        'previous_day': previous_day,
        'next_day': next_day,
        'event_type_filter': event_type_filter,
        'priority_filter': priority_filter,
        'status_filter': status_filter,
        'search': search,
        'date_filter': date_filter,
        'user_property': request.user.property,
        'is_today': target_date == timezone.localtime().date(),
    }
    
    return render(request, 'dashboards/employee_todays_schedule_detail.html', context)

@login_required
def employee_pending_requests_detail(request):
    """Expanded view for employee pending maintenance requests"""
    
    # Ensure user is an employee
    if request.user.role != User.Role.EMPLOYEE:
        return redirect('core:dashboard_redirect')
    
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Get all maintenance requests for the company
    maintenance_requests = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    ).select_related('property', 'apartment_unit', 'assigned_to', 'tenant', 'category')
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        maintenance_requests = maintenance_requests.filter(property=request.user.property)
    
    # Base queryset for pending requests (unassigned SUBMITTED requests)
    pending_requests = maintenance_requests.filter(
        status='SUBMITTED',
        assigned_to__isnull=True
    )
    
    # Apply filters
    priority_filter = request.GET.get('priority', '')
    category_filter = request.GET.get('category', '')
    property_filter = request.GET.get('property', '')
    age_filter = request.GET.get('age', '')
    search = request.GET.get('search', '')
    
    if priority_filter:
        pending_requests = pending_requests.filter(priority=priority_filter)
    
    if category_filter:
        pending_requests = pending_requests.filter(category_id=category_filter)
    
    if property_filter:
        pending_requests = pending_requests.filter(property_id=property_filter)
    
    if age_filter:
        if age_filter == '24h':
            cutoff = timezone.now() - timedelta(hours=24)
            pending_requests = pending_requests.filter(created_at__gte=cutoff)
        elif age_filter == '3d':
            cutoff = timezone.now() - timedelta(days=3)
            pending_requests = pending_requests.filter(created_at__gte=cutoff)
        elif age_filter == '1w':
            cutoff = timezone.now() - timedelta(days=7)
            pending_requests = pending_requests.filter(created_at__gte=cutoff)
        elif age_filter == 'old':
            cutoff = timezone.now() - timedelta(days=7)
            pending_requests = pending_requests.filter(created_at__lt=cutoff)
    
    if search:
        pending_requests = pending_requests.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(apartment_unit__unit_number__icontains=search) |
            Q(tenant__first_name__icontains=search) |
            Q(tenant__last_name__icontains=search)
        )
    
    # Order by priority and age (oldest first within same priority)
    pending_requests = pending_requests.order_by(
        '-priority',  # Emergency first, then High, Medium, Low
        'created_at'  # Oldest first within same priority
    )
    
    # Calculate summary statistics
    total_pending = pending_requests.count()
    
    # Priority breakdown
    priority_counts = {
        'EMERGENCY': pending_requests.filter(priority='EMERGENCY').count(),
        'HIGH': pending_requests.filter(priority='HIGH').count(),
        'MEDIUM': pending_requests.filter(priority='MEDIUM').count(),
        'LOW': pending_requests.filter(priority='LOW').count(),
    }
    
    # Age breakdown
    now = timezone.now()
    age_counts = {
        'new': pending_requests.filter(created_at__gte=now - timedelta(hours=24)).count(),
        'recent': pending_requests.filter(
            created_at__gte=now - timedelta(days=3),
            created_at__lt=now - timedelta(hours=24)
        ).count(),
        'old': pending_requests.filter(created_at__lt=now - timedelta(days=7)).count(),
    }
    
    # Property breakdown (if user has access to multiple properties)
    property_counts = {}
    if not request.user.property:  # Employee has company-wide access
        property_breakdown = pending_requests.values('property__name').annotate(
            count=Count('id')
        ).order_by('-count')
        for item in property_breakdown:
            property_counts[item['property__name']] = item['count']
    
    # Category breakdown
    category_breakdown = pending_requests.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')
    category_counts = {}
    for item in category_breakdown:
        category_counts[item['category__name'] or 'No Category'] = item['count']
    
    # Get oldest pending request for urgency indicator
    oldest_request = pending_requests.order_by('created_at').first()
    oldest_days = None
    if oldest_request:
        oldest_days = (timezone.now() - oldest_request.created_at).days
    
    # Get available categories and properties for filter dropdown
    categories = MaintenanceCategory.objects.all()
    
    # Get available properties (only if employee has company-wide access)
    available_properties = []
    if not request.user.property:
        available_properties = request.user.company.properties.all()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(pending_requests, 12)  # Show 12 requests per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'pending_requests': page_obj,
        'total_pending': total_pending,
        'priority_counts': priority_counts,
        'age_counts': age_counts,
        'property_counts': property_counts,
        'category_counts': category_counts,
        'oldest_days': oldest_days,
        'categories': categories,
        'available_properties': available_properties,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'property_filter': property_filter,
        'age_filter': age_filter,
        'search': search,
        'user_property': request.user.property,
    }
    
    return render(request, 'dashboards/employee_pending_requests_detail.html', context)

@login_required
def employee_emergency_requests_detail(request):
    """Expanded view for employee emergency maintenance requests"""
    
    # Ensure user is an employee
    if request.user.role != User.Role.EMPLOYEE:
        return redirect('core:dashboard_redirect')
    
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Get all maintenance requests for the company
    maintenance_requests = MaintenanceRequest.objects.filter(
        property__company=request.user.company
    ).select_related('property', 'apartment_unit', 'assigned_to', 'tenant', 'category')
    
    # Filter by property if employee is assigned to specific property
    if request.user.property:
        maintenance_requests = maintenance_requests.filter(property=request.user.property)
    
    # Base queryset for emergency requests (priority='EMERGENCY')
    emergency_requests = maintenance_requests.filter(priority='EMERGENCY')
    
    # Apply filters
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')
    property_filter = request.GET.get('property', '')
    assignment_filter = request.GET.get('assignment', '')
    age_filter = request.GET.get('age', '')
    search = request.GET.get('search', '')
    
    if status_filter:
        emergency_requests = emergency_requests.filter(status=status_filter)
    
    if category_filter:
        emergency_requests = emergency_requests.filter(category_id=category_filter)
    
    if property_filter:
        emergency_requests = emergency_requests.filter(property_id=property_filter)
    
    if assignment_filter:
        if assignment_filter == 'assigned':
            emergency_requests = emergency_requests.filter(assigned_to__isnull=False)
        elif assignment_filter == 'unassigned':
            emergency_requests = emergency_requests.filter(assigned_to__isnull=True)
        elif assignment_filter == 'assigned_to_me':
            emergency_requests = emergency_requests.filter(assigned_to=request.user)
    
    if age_filter:
        if age_filter == '1h':
            cutoff = timezone.now() - timedelta(hours=1)
            emergency_requests = emergency_requests.filter(created_at__gte=cutoff)
        elif age_filter == '6h':
            cutoff = timezone.now() - timedelta(hours=6)
            emergency_requests = emergency_requests.filter(created_at__gte=cutoff)
        elif age_filter == '24h':
            cutoff = timezone.now() - timedelta(hours=24)
            emergency_requests = emergency_requests.filter(created_at__gte=cutoff)
        elif age_filter == 'old':
            cutoff = timezone.now() - timedelta(hours=24)
            emergency_requests = emergency_requests.filter(created_at__lt=cutoff)
    
    if search:
        emergency_requests = emergency_requests.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(apartment_unit__unit_number__icontains=search) |
            Q(tenant__first_name__icontains=search) |
            Q(tenant__last_name__icontains=search)
        )
    
    # Order by created date (newest first for emergency)
    emergency_requests = emergency_requests.order_by('-created_at')
    
    # Calculate summary statistics
    total_emergency = emergency_requests.count()
    
    # Status breakdown
    status_counts = {
        'SUBMITTED': emergency_requests.filter(status='SUBMITTED').count(),
        'IN_PROGRESS': emergency_requests.filter(status='IN_PROGRESS').count(),
        'SCHEDULED': emergency_requests.filter(status='SCHEDULED').count(),
        'COMPLETED': emergency_requests.filter(status='COMPLETED').count(),
    }
    
    # Assignment breakdown
    assignment_counts = {
        'unassigned': emergency_requests.filter(assigned_to__isnull=True).count(),
        'assigned': emergency_requests.filter(assigned_to__isnull=False).count(),
        'assigned_to_me': emergency_requests.filter(assigned_to=request.user).count(),
    }
    
    # Time-based breakdown (critical for emergency requests)
    now = timezone.now()
    time_counts = {
        'last_hour': emergency_requests.filter(created_at__gte=now - timedelta(hours=1)).count(),
        'last_6_hours': emergency_requests.filter(created_at__gte=now - timedelta(hours=6)).count(),
        'last_24_hours': emergency_requests.filter(created_at__gte=now - timedelta(hours=24)).count(),
        'older': emergency_requests.filter(created_at__lt=now - timedelta(hours=24)).count(),
    }
    
    # Property breakdown (if user has access to multiple properties)
    property_counts = {}
    if not request.user.property:  # Employee has company-wide access
        property_breakdown = emergency_requests.values('property__name').annotate(
            count=Count('id')
        ).order_by('-count')
        for item in property_breakdown:
            property_counts[item['property__name']] = item['count']
    
    # Category breakdown
    category_breakdown = emergency_requests.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')
    category_counts = {}
    for item in category_breakdown:
        category_counts[item['category__name'] or 'No Category'] = item['count']
    
    # Response time analysis for completed requests
    completed_emergency = emergency_requests.filter(status='COMPLETED')
    avg_response_time_hours = None
    if completed_emergency.exists():
        response_times = []
        for req in completed_emergency:
            if req.completed_at:
                response_time = (req.completed_at - req.created_at).total_seconds() / 3600  # hours
                response_times.append(response_time)
        if response_times:
            avg_response_time_hours = sum(response_times) / len(response_times)
    
    # Critical alerts
    critical_unassigned = emergency_requests.filter(
        assigned_to__isnull=True,
        created_at__lt=now - timedelta(hours=1)
    ).count()
    
    overdue_in_progress = emergency_requests.filter(
        status='IN_PROGRESS',
        created_at__lt=now - timedelta(hours=12)
    ).count()
    
    # Get available categories and properties for filter dropdown
    categories = MaintenanceCategory.objects.all()
    
    # Get available properties (only if employee has company-wide access)
    available_properties = []
    if not request.user.property:
        available_properties = request.user.company.properties.all()
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(emergency_requests, 10)  # Show 10 requests per page for emergency
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'emergency_requests': page_obj,
        'total_emergency': total_emergency,
        'status_counts': status_counts,
        'assignment_counts': assignment_counts,
        'time_counts': time_counts,
        'property_counts': property_counts,
        'category_counts': category_counts,
        'avg_response_time_hours': avg_response_time_hours,
        'critical_unassigned': critical_unassigned,
        'overdue_in_progress': overdue_in_progress,
        'categories': categories,
        'available_properties': available_properties,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'property_filter': property_filter,
        'assignment_filter': assignment_filter,
        'age_filter': age_filter,
        'search': search,
        'user_property': request.user.property,
    }
    
    return render(request, 'dashboards/employee_emergency_requests_detail.html', context)

@login_required
def employee_list(request):
    """Employee management list view for landlords"""
    if not request.user.company:
        messages.error(request, "You must be assigned to a company to access this page.")
        return redirect("core:login")
    
    # Only allow landlords to access this view
    if request.user.role != User.Role.LANDLORD:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("core:dashboard_redirect")
    
    # Get filter parameters from URL
    property_id = request.GET.get('property')
    search_query = request.GET.get('search')
    
    selected_property = None
    if property_id:
        try:
            from properties.models import Property
            selected_property = Property.objects.get(
                id=property_id, 
                company=request.user.company
            )
        except Property.DoesNotExist:
            selected_property = None
    
    # Base query for employees
    employees_query = User.objects.filter(
        company=request.user.company,
        role=User.Role.EMPLOYEE
    ).select_related(
        'property',
    ).order_by('last_name', 'first_name', 'username')
    
    # Apply property filter
    if selected_property:
        employees_query = employees_query.filter(property=selected_property)
    
    # Apply search filter
    if search_query:
        employees_query = employees_query.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Get all employees for this company
    employees = employees_query
    
    # Get available properties for filter dropdown
    from properties.models import Property
    available_properties = Property.objects.filter(company=request.user.company)
    
    # Summary statistics
    total_employees = employees.count()
    employees_by_property = employees.exclude(property__isnull=True).values('property__name').annotate(
        count=Count('id')
    ).order_by('property__name')
    
    # Recent activity - employees who joined in last 30 days
    recent_cutoff = timezone.now() - timedelta(days=30)
    recent_employees = employees.filter(date_joined__gte=recent_cutoff).order_by('-date_joined')[:5]
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(employees, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'employees': page_obj,
        'total_employees': total_employees,
        'employees_by_property': employees_by_property,
        'recent_employees': recent_employees,
        'selected_property': selected_property,
        'available_properties': available_properties,
        'search_query': search_query,
    }
    
    return render(request, 'dashboards/employee_list.html', context)
