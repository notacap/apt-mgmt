from django.contrib import admin
from .models import (
    Notification, MessageThread, Message, MessageAttachment, MessageReadStatus,
    CommunityPost, CommunityPostAttachment
)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username', 'recipient__email')
    readonly_fields = ('created_at',)

@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ('subject', 'created_at', 'updated_at', 'participant_count')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('subject', 'participants__username', 'participants__email')
    readonly_fields = ('created_at', 'updated_at')
    
    def participant_count(self, obj):
        return obj.participants.count()
    participant_count.short_description = 'Participants'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'thread', 'created_at', 'is_edited')
    list_filter = ('created_at', 'is_edited')
    search_fields = ('content', 'sender__username', 'sender__email')
    readonly_fields = ('created_at', 'edited_at')

@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'message', 'file_size', 'uploaded_at')
    list_filter = ('uploaded_at', 'content_type')
    search_fields = ('filename',)
    readonly_fields = ('uploaded_at',)

@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('user__username', 'user__email')

@admin.register(CommunityPost)
class CommunityPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'property', 'post_type', 'status', 'is_pinned', 'created_at')
    list_filter = ('post_type', 'status', 'is_pinned', 'created_at', 'property')
    search_fields = ('title', 'content', 'author__username', 'author__email')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'property')

@admin.register(CommunityPostAttachment)
class CommunityPostAttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'post', 'file_size', 'uploaded_at')
    list_filter = ('uploaded_at', 'content_type')
    search_fields = ('filename',)
    readonly_fields = ('uploaded_at',)
