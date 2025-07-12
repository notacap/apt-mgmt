from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from users.forms import LandlordCreationForm, InvitationForm, UserProfileForm, InvitationAcceptanceForm
from users.models import User, Invitation
from django.contrib.auth.models import Group

# Create your views here.

def index(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard_redirect")
    return redirect("core:login")

def landlord_dashboard(request):
    return render(request, "dashboards/landlord.html")

def employee_dashboard(request):
    return render(request, "dashboards/employee.html")

def tenant_dashboard(request):
    return render(request, "dashboards/tenant.html")

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
