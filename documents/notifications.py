"""
Document notification utilities
"""
from communication.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()


def create_document_assignment_notification(document, assigned_user, assigner=None):
    """
    Create a notification when a document is assigned to a user
    
    Args:
        document: The Document instance
        assigned_user: User who is being assigned the document
        assigner: User who assigned the document (optional, defaults to document uploader)
    """
    if not assigner:
        assigner = document.uploaded_by
    
    # Don't notify if user is assigning to themselves
    if assigned_user == assigner:
        return None
    
    # Create appropriate message based on assigner role and context
    if assigner.role == 'TENANT':
        message = f'{assigner.get_full_name() or assigner.username} uploaded a document and assigned it to you.'
        title = f'New document assigned: {document.title}'
    else:
        message = f'{assigner.get_full_name() or assigner.username} assigned a document to you.'
        title = f'Document assigned: {document.title}'
    
    notification = Notification.objects.create(
        recipient=assigned_user,
        notification_type=Notification.NotificationType.DOCUMENT_SHARED,
        title=title,
        message=message,
        link_url=f'/documents/{document.id}/'
    )
    
    return notification


def create_document_share_notification(document_share):
    """
    Create a notification when a document is shared with a user
    
    Args:
        document_share: The DocumentShare instance
    """
    notification = Notification.objects.create(
        recipient=document_share.shared_with,
        notification_type=Notification.NotificationType.DOCUMENT_SHARED,
        title=f'Document shared: {document_share.document.title}',
        message=f'{document_share.shared_by.get_full_name() or document_share.shared_by.username} shared a document with you.',
        link_url=f'/documents/{document_share.document.id}/'
    )
    
    return notification


def notify_document_assignments(document, assigned_users, assigner=None):
    """
    Create notifications for multiple users being assigned to a document
    
    Args:
        document: The Document instance
        assigned_users: QuerySet or list of User instances being assigned
        assigner: User who assigned the document (optional, defaults to document uploader)
    """
    notifications = []
    
    for user in assigned_users:
        notification = create_document_assignment_notification(document, user, assigner)
        if notification:
            notifications.append(notification)
    
    return notifications