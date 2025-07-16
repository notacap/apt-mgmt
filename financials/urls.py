from django.urls import path
from . import views

app_name = 'financials'

urlpatterns = [
    # Payment Schedule URLs
    path('payment-schedules/', views.payment_schedule_list, name='payment_schedule_list'),
    path('payment-schedules/create/', views.create_payment_schedule, name='create_payment_schedule'),
    path('payment-schedules/<int:pk>/', views.payment_schedule_detail, name='payment_schedule_detail'),
    path('payment-schedules/<int:pk>/edit/', views.edit_payment_schedule, name='edit_payment_schedule'),
    path('payment-schedules/<int:pk>/delete/', views.delete_payment_schedule, name='delete_payment_schedule'),
    
    # Rent Payment URLs
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/<int:pk>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:pk>/process/', views.process_payment, name='process_payment'),
    path('payments/tenant/', views.tenant_payments, name='tenant_payments'),
    path('payments/tenant/portal/', views.payment_portal, name='payment_portal'),
    path('payments/tenant/pay/<int:pk>/', views.tenant_make_payment, name='tenant_make_payment'),
    
    # Expense URLs
    path('expenses/', views.expense_list, name='expense_list'),
    path('expenses/create/', views.create_expense, name='create_expense'),
    path('expenses/<int:pk>/', views.expense_detail, name='expense_detail'),
    path('expenses/<int:pk>/edit/', views.edit_expense, name='edit_expense'),
    path('expenses/<int:pk>/delete/', views.delete_expense, name='delete_expense'),
    
    # Receipt URLs
    path('receipts/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    path('receipts/<int:payment_id>/download/', views.download_receipt, name='download_receipt'),
    
    # HTMX URLs for dynamic forms
    path('htmx/units-by-property/', views.units_by_property, name='units_by_property'),
    
    # Financial Reports
    path('reports/', views.financial_reports, name='financial_reports'),
    path('reports/income/', views.income_report, name='income_report'),
    path('reports/expenses/', views.expense_report, name='expense_report'),
]