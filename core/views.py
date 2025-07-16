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
from maintenance.models import MaintenanceRequest
from communication.models import MessageThread
from properties.models import ApartmentUnit
from financials.models import PaymentSchedule
from datetime import timedelta, date
from django.utils import timezone
from django.http import JsonResponse

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
    
    # Maintenance statistics
    total_maintenance_requests = company_maintenance_requests.count()
    pending_requests = company_maintenance_requests.filter(status='SUBMITTED').count()
    in_progress_requests = company_maintenance_requests.filter(status='IN_PROGRESS').count()
    emergency_requests = company_maintenance_requests.filter(priority='EMERGENCY').count()
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
            messages.success(request, "Invitation sent successfully.")
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
                
                # Create payment schedule
                if invitation.rent_amount and invitation.rent_payment_date and invitation.lease_length_months:
                    start_date = date.today()
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
                        rent_amount=invitation.rent_amount,
                        frequency='MONTHLY',
                        payment_day=invitation.rent_payment_date,
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
    ).values('id', 'unit_number', 'rent_amount', 'bedrooms', 'bathrooms')
    
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
