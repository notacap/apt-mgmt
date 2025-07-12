from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import (
    index, 
    landlord_dashboard, 
    employee_dashboard, 
    tenant_dashboard, 
    create_landlord, 
    send_invitation, 
    profile,
    dashboard_redirect,
    accept_invitation
)

app_name = "core"

urlpatterns = [
    path("login/", LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", LogoutView.as_view(next_page="core:login"), name="logout"),
    path("accept-invitation/<uuid:token>/", accept_invitation, name="accept_invitation"),
    path("dashboard/", dashboard_redirect, name="dashboard_redirect"),
    path("", index, name="index"),
    path("profile/", profile, name="profile"),
    path("create-landlord/", create_landlord, name="create_landlord"),
    path("send-invitation/", send_invitation, name="send_invitation"),
    path("dashboard/landlord/", landlord_dashboard, name="landlord_dashboard"),
    path("dashboard/employee/", employee_dashboard, name="employee_dashboard"),
    path("dashboard/tenant/", tenant_dashboard, name="tenant_dashboard"),
] 