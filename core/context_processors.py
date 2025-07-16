"""
Context processors for the core app
"""
from communication.models import Notification


def notifications(request):
    """
    Add notification data to all template contexts
    """
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).order_by('-created_at')
        
        # For dropdown: only show recent unread notifications (max 5)
        recent_unread_notifications = unread_notifications[:5]
        
        return {
            'unread_notifications_count': unread_notifications.count(),
            'recent_notifications': recent_unread_notifications,
            'has_unread_notifications': unread_notifications.exists(),
        }
    
    return {
        'unread_notifications_count': 0,
        'recent_notifications': [],
        'has_unread_notifications': False,
    }