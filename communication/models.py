from django.db import models
from django.contrib.auth import get_user_model
from properties.models import Property
import uuid

User = get_user_model()

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        MAINTENANCE_REQUEST = "MAINTENANCE_REQUEST", "Maintenance Request"
        RENT_PAYMENT = "RENT_PAYMENT", "Rent Payment"
        MESSAGE = "MESSAGE", "Message"
        LEASE_EXPIRATION = "LEASE_EXPIRATION", "Lease Expiration"
        WORK_ASSIGNMENT = "WORK_ASSIGNMENT", "Work Assignment"
        DOCUMENT_SHARED = "DOCUMENT_SHARED", "Document Shared"
        GENERAL = "GENERAL", "General"

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional fields for linking to specific objects
    link_url = models.URLField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"


class MessageThread(models.Model):
    """Represents a conversation between users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(User, related_name="message_threads")
    subject = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        participants_list = ", ".join([user.get_full_name() or user.username for user in self.participants.all()[:3]])
        if self.participants.count() > 3:
            participants_list += f" (+{self.participants.count() - 3} more)"
        return f"{self.subject or 'No Subject'} - {participants_list}"
    
    @property
    def last_message(self):
        return self.messages.first()


class Message(models.Model):
    """Individual message within a thread"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.sender.get_full_name() or self.sender.username} at {self.created_at}"


class MessageAttachment(models.Model):
    """File attachments for messages"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to='message_attachments/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment: {self.filename}"


class MessageReadStatus(models.Model):
    """Track read status for each user in a thread"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'message')
    
    def __str__(self):
        return f"{self.user.username} read message at {self.read_at}"


class CommunityPost(models.Model):
    """Community board posts for property-specific announcements"""
    class PostType(models.TextChoices):
        ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
        EVENT = "EVENT", "Event"
        NOTICE = "NOTICE", "Notice"
        GENERAL = "GENERAL", "General"
    
    class PostStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ARCHIVED = "ARCHIVED", "Archived"
        HIDDEN = "HIDDEN", "Hidden"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="community_posts")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_posts")
    title = models.CharField(max_length=200)
    content = models.TextField()
    post_type = models.CharField(max_length=20, choices=PostType.choices, default=PostType.GENERAL)
    status = models.CharField(max_length=20, choices=PostStatus.choices, default=PostStatus.ACTIVE)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Optional fields for events
    event_date = models.DateTimeField(null=True, blank=True)
    event_location = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['property', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.property.name}"
    
    def can_be_edited_by(self, user):
        """Check if user can edit this post"""
        # Only authors can edit their own posts
        return self.author == user
    
    def can_be_moderated_by(self, user):
        """Check if user can moderate (hide/delete) this post"""
        # Authors can moderate their own posts
        if self.author == user:
            return True
        # Landlords and employees can moderate posts in their property
        if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
            if user.role == User.Role.LANDLORD and user.company == self.property.company:
                return True
            if user.role == User.Role.EMPLOYEE and user.property == self.property:
                return True
        return False


class CommunityPostAttachment(models.Model):
    """File attachments for community posts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(CommunityPost, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to='community_attachments/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    @property
    def is_image(self):
        """Check if the attachment is an image"""
        return self.content_type.startswith('image/')
    
    def __str__(self):
        return f"Attachment: {self.filename}"
