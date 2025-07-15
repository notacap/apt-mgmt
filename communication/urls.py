from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    path('', views.message_list, name='message_list'),
    path('new/', views.new_thread, name='new_thread'),
    path('thread/<uuid:thread_id>/', views.thread_detail, name='thread_detail'),
    path('api/recipients/', views.get_recipients, name='get_recipients'),
    
    # Community Board URLs
    path('community/', views.community_board, name='community_board'),
    path('community/new/', views.create_community_post, name='create_community_post'),
    path('community/post/<uuid:post_id>/', views.community_post_detail, name='community_post_detail'),
    path('community/post/<uuid:post_id>/edit/', views.edit_community_post, name='edit_community_post'),
    path('community/post/<uuid:post_id>/delete/', views.delete_community_post, name='delete_community_post'),
]