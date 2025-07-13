from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    path('', views.message_list, name='message_list'),
    path('new/', views.new_thread, name='new_thread'),
    path('thread/<uuid:thread_id>/', views.thread_detail, name='thread_detail'),
    path('api/recipients/', views.get_recipients, name='get_recipients'),
]