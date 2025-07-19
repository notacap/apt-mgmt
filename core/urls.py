from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    index, 
    landlord_dashboard, 
    employee_dashboard, 
    tenant_dashboard, 
    create_landlord, 
    send_invitation, 
    profile,
    dashboard_redirect,
    accept_invitation,
    get_available_units,
    custom_login,
    rent_income_detail,
    monthly_expenses_detail,
    maintenance_requests_detail,
    payment_status_detail,
    occupancy_rate_detail,
    lease_expirations_detail
)

app_name = "core"

urlpatterns = [
    path("login/", custom_login, name="login"),
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
    path("dashboard/rent-income/", rent_income_detail, name="rent_income_detail"),
    path("dashboard/monthly-expenses/", monthly_expenses_detail, name="monthly_expenses_detail"),
    path("dashboard/maintenance-requests/", maintenance_requests_detail, name="maintenance_requests_detail"),
    path("dashboard/payment-status/", payment_status_detail, name="payment_status_detail"),
    path("dashboard/occupancy-rate/", occupancy_rate_detail, name="occupancy_rate_detail"),
    path("dashboard/lease-expirations/", lease_expirations_detail, name="lease_expirations_detail"),
    # API endpoints
    path("api/properties/<int:property_id>/available-units/", get_available_units, name="get_available_units"),
] 