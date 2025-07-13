from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from users.forms import LandlordCreationForm, InvitationForm, UserProfileForm, InvitationAcceptanceForm
from users.models import User, Invitation
from django.contrib.auth.models import Group
from documents.models import Document, DocumentShare
from datetime import timedelta
from django.utils import timezone

# Create your views here.

def index(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard_redirect")
    return redirect("core:login")

@login_required
def landlord_dashboard(request):
    """Landlord dashboard with real document data"""
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
    
    context = {
        'recent_documents': recent_documents,
        'company_doc_count': company_doc_count,
        'property_doc_count': property_doc_count,
        'private_doc_count': private_doc_count,
        'shared_with_employees': shared_with_employees,
        'shared_with_tenants': shared_with_tenants,
        'total_documents': company_documents.count(),
    }
    
    return render(request, "dashboards/landlord.html", context)

@login_required
def employee_dashboard(request):
    """Employee dashboard with real document data"""
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
    
    context = {
        'employee_uploads': employee_uploads,
        'shared_documents': shared_documents,
        'property_documents': property_documents[:5],  # Limit for display
        'landlord_shared_count': landlord_shared,
        'property_doc_count': property_doc_count,
        'total_accessible': property_documents.count(),
        'user_property': request.user.property,
    }
    
    return render(request, "dashboards/employee.html", context)

@login_required
def tenant_dashboard(request):
    """Tenant dashboard with real document data"""
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
    
    context = {
        'personal_documents': personal_documents,
        'shared_documents': shared_documents,
        'community_documents': community_documents,
        'personal_doc_count': personal_doc_count,
        'shared_with_tenant_count': shared_with_tenant_count,
        'recent_shares_count': recent_shares,
        'user_property': request.user.property,
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
