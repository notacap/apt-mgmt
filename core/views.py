from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q, Count
from users.forms import LandlordCreationForm, InvitationForm, UserProfileForm, InvitationAcceptanceForm
from users.models import User, Invitation
from django.contrib.auth.models import Group
from documents.models import Document, DocumentShare
from maintenance.models import MaintenanceRequest, MaintenanceInvoice
from communication.models import MessageThread
from properties.models import ApartmentUnit
from financials.models import PaymentSchedule, RentPayment, ExpenseRecord
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Sum, Q
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
            
        except Property.DoesNotExist:
            selected_property = None
    
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
        # Property selection data
        'available_properties': available_properties,
        'selected_property': selected_property,
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
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("core:profile")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})

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
