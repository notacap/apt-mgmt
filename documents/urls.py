from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('upload/', views.document_upload, name='upload'),
    path('<int:document_id>/', views.document_detail, name='detail'),
    path('<int:document_id>/download/', views.document_download, name='download'),
    path('<int:document_id>/share/', views.document_share, name='share'),
    path('<int:document_id>/delete/', views.document_delete, name='delete'),
    path('categories/', views.category_list, name='category_list'),
    path('shared/', views.shared_documents, name='shared'),
    path('api/units/<int:property_id>/', views.get_units_for_property, name='api_units'),
]