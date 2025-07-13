from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    path('', views.maintenance_list, name='list'),
    path('create/', views.maintenance_create, name='create'),
    path('<int:pk>/', views.maintenance_detail, name='detail'),
    path('<int:pk>/update-status/', views.maintenance_update_status, name='update_status'),
    path('<int:pk>/add-update/', views.maintenance_add_update, name='add_update'),
    path('<int:pk>/add-invoice/', views.maintenance_add_invoice, name='add_invoice'),
]