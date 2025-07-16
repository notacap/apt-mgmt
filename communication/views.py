from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Max, Count
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from .models import MessageThread, Message, MessageAttachment, MessageReadStatus, Notification, CommunityPost, CommunityPostAttachment
from .forms import MessageForm, NewThreadForm, CommunityPostForm
import json

User = get_user_model()

@login_required
def message_list(request):
    """Display all message threads for the current user"""
    user = request.user
    
    # Get threads where user is a participant
    threads = MessageThread.objects.filter(
        participants=user
    ).prefetch_related(
        'participants', 'messages'
    ).annotate(
        unread_count=Count('messages', filter=Q(
            messages__messagereadstatus__isnull=True,
            messages__messagereadstatus__user=user
        ) | Q(
            ~Q(messages__messagereadstatus__user=user)
        ))
    )
    
    context = {
        'threads': threads,
        'user': user,
    }
    return render(request, 'communication/message_list.html', context)

@login_required
def thread_detail(request, thread_id):
    """Display messages in a specific thread"""
    thread = get_object_or_404(MessageThread, id=thread_id, participants=request.user)
    
    # Mark messages as read
    unread_messages = Message.objects.filter(
        thread=thread
    ).exclude(
        messagereadstatus__user=request.user
    ).exclude(
        sender=request.user
    )
    
    for message in unread_messages:
        MessageReadStatus.objects.get_or_create(
            user=request.user,
            message=message
        )
    
    messages = thread.messages.all().order_by('created_at')
    
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.thread = thread
            message.sender = request.user
            message.save()
            
            # Handle file attachments
            files = request.FILES.getlist('attachments')
            for file in files:
                MessageAttachment.objects.create(
                    message=message,
                    file=file,
                    filename=file.name,
                    file_size=file.size,
                    content_type=file.content_type
                )
            
            # Update thread timestamp
            thread.save()
            
            # Send notification to other participants
            for participant in thread.participants.exclude(id=request.user.id):
                Notification.objects.create(
                    recipient=participant,
                    notification_type=Notification.NotificationType.MESSAGE,
                    title=f"New message from {request.user.get_full_name() or request.user.username}",
                    message=f"Subject: {thread.subject or 'No Subject'}",
                    link_url=f'/messages/thread/{thread.id}/'
                )
            
            return redirect('communication:thread_detail', thread_id=thread.id)
    else:
        form = MessageForm()
    
    context = {
        'thread': thread,
        'messages': messages,
        'form': form,
    }
    return render(request, 'communication/thread_detail.html', context)

@login_required
def new_thread(request):
    """Create a new message thread"""
    if request.method == 'POST':
        form = NewThreadForm(request.POST, user=request.user)
        if form.is_valid():
            thread = MessageThread.objects.create(
                subject=form.cleaned_data['subject']
            )
            
            # Add participants
            recipients = form.cleaned_data['recipients']
            thread.participants.add(request.user)
            thread.participants.add(*recipients)
            
            # Create initial message
            if form.cleaned_data['content']:
                message = Message.objects.create(
                    thread=thread,
                    sender=request.user,
                    content=form.cleaned_data['content']
                )
                
                # Handle file attachments
                files = request.FILES.getlist('attachments')
                for file in files:
                    MessageAttachment.objects.create(
                        message=message,
                        file=file,
                        filename=file.name,
                        file_size=file.size,
                        content_type=file.content_type
                    )
                
                # Send notifications
                for recipient in recipients:
                    Notification.objects.create(
                        recipient=recipient,
                        notification_type=Notification.NotificationType.MESSAGE,
                        title=f"New message from {request.user.get_full_name() or request.user.username}",
                        message=f"Subject: {thread.subject or 'No Subject'}",
                        link_url=f'/messages/thread/{thread.id}/'
                    )
            
            django_messages.success(request, 'Message thread created successfully.')
            return redirect('communication:thread_detail', thread_id=thread.id)
    else:
        form = NewThreadForm(user=request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'communication/new_thread.html', context)

@login_required
@require_http_methods(["GET"])
def get_recipients(request):
    """API endpoint to get available recipients based on user role"""
    user = request.user
    recipients = []
    
    if user.role == User.Role.TENANT:
        # Tenants can message landlords and employees of their property
        if user.property:
            recipients = User.objects.filter(
                Q(role=User.Role.LANDLORD, company=user.company) |
                Q(role=User.Role.EMPLOYEE, property=user.property)
            ).exclude(id=user.id)
    
    elif user.role == User.Role.EMPLOYEE:
        # Employees can message landlords, tenants, and other employees from their property
        recipients_query = Q()
        
        if user.company:
            recipients_query |= Q(role=User.Role.LANDLORD, company=user.company)
        
        if user.property:
            recipients_query |= Q(role=User.Role.TENANT, property=user.property)
            # Other employees from the same property
            recipients_query |= Q(role=User.Role.EMPLOYEE, property=user.property)
        
        recipients = User.objects.filter(recipients_query).exclude(id=user.id)
    
    elif user.role == User.Role.LANDLORD:
        # Landlords can message all users in their company
        recipients = User.objects.filter(
            company=user.company
        ).exclude(id=user.id)
    
    elif user.role == User.Role.SUPERUSER:
        # Superusers can message anyone
        recipients = User.objects.exclude(id=user.id)
    
    # Format response
    recipients_data = [
        {
            'id': r.id,
            'name': r.get_full_name() or r.username,
            'role': r.get_role_display(),
            'email': r.email,
            'property': r.property.name if r.property else None,
            'company': r.company.name if r.company else None,
        }
        for r in recipients.select_related('company', 'property')
    ]
    
    return JsonResponse({'recipients': recipients_data})


@login_required
def community_board(request):
    """Display community board posts for user's property"""
    user = request.user
    
    # Determine which posts to show based on user role
    if user.role == User.Role.TENANT and user.property:
        # Tenants see posts for their property
        posts = CommunityPost.objects.filter(
            property=user.property,
            status=CommunityPost.PostStatus.ACTIVE
        ).select_related('author', 'property').prefetch_related('attachments')
        property_filter = user.property
    elif user.role == User.Role.EMPLOYEE and user.property:
        # Employees see posts for their assigned property
        posts = CommunityPost.objects.filter(
            property=user.property,
            status=CommunityPost.PostStatus.ACTIVE
        ).select_related('author', 'property').prefetch_related('attachments')
        property_filter = user.property
    elif user.role == User.Role.LANDLORD and user.company:
        # Landlords see posts from all properties in their company
        posts = CommunityPost.objects.filter(
            property__company=user.company,
            status=CommunityPost.PostStatus.ACTIVE
        ).select_related('author', 'property').prefetch_related('attachments')
        property_filter = None  # Multiple properties
    else:
        posts = CommunityPost.objects.none()
        property_filter = None
    
    # Add permission checks for each post
    for post in posts:
        post.user_can_edit = post.can_be_edited_by(user)
        post.user_can_moderate = post.can_be_moderated_by(user)
    
    # Check posting permissions
    can_post = False
    if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.TENANT]:
        can_post = True
    
    context = {
        'posts': posts,
        'can_post': can_post,
        'property': property_filter,
    }
    return render(request, 'communication/community_board.html', context)


@login_required
def create_community_post(request):
    """Create a new community board post"""
    user = request.user
    
    # Check permissions - landlords, employees, and tenants can post
    if user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.TENANT]:
        django_messages.error(request, 'You do not have permission to create posts.')
        return redirect('communication:community_board')
    
    # Determine the property for the post
    if user.role == User.Role.TENANT and user.property:
        post_property = user.property
        available_properties = [user.property]
    elif user.role == User.Role.EMPLOYEE and user.property:
        post_property = user.property
        available_properties = [user.property]
    elif user.role == User.Role.LANDLORD and user.company:
        # Landlords can post to any property in their company
        from properties.models import Property
        available_properties = Property.objects.filter(company=user.company)
        
        # If landlord has a specific property assigned, use that as default
        post_property = user.property if user.property else available_properties.first()
        
        # If property is specified in the request, use that
        if request.method == 'GET' and 'property' in request.GET:
            try:
                selected_property_id = request.GET['property']
                post_property = available_properties.get(id=selected_property_id)
            except Property.DoesNotExist:
                pass
    else:
        django_messages.error(request, 'You must be assigned to a company/property to create posts.')
        return redirect('communication:community_board')
    
    if not post_property:
        django_messages.error(request, 'No property available for posting.')
        return redirect('communication:community_board')
    
    if request.method == 'POST':
        # Handle property selection for landlords
        if user.role == User.Role.LANDLORD and 'property_id' in request.POST:
            try:
                selected_property_id = request.POST['property_id']
                post_property = available_properties.get(id=selected_property_id)
            except Property.DoesNotExist:
                django_messages.error(request, 'Invalid property selected.')
                return redirect('communication:create_community_post')
        
        form = CommunityPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = user
            post.property = post_property
            post.save()
            
            # Handle file attachments
            files = request.FILES.getlist('attachments')
            for file in files:
                CommunityPostAttachment.objects.create(
                    post=post,
                    file=file,
                    filename=file.name,
                    file_size=file.size,
                    content_type=file.content_type
                )
            
            django_messages.success(request, 'Community post created successfully.')
            return redirect('communication:community_board')
    else:
        form = CommunityPostForm()
    
    context = {
        'form': form,
        'property': post_property,
        'available_properties': available_properties,
        'is_landlord': user.role == User.Role.LANDLORD,
    }
    return render(request, 'communication/create_post.html', context)


@login_required
def community_post_detail(request, post_id):
    """View detailed community post"""
    user = request.user
    
    # Get the post and check if user can view it
    post = get_object_or_404(CommunityPost, id=post_id, status=CommunityPost.PostStatus.ACTIVE)
    
    # Check if user can view posts for this property
    can_view = False
    if user.role == User.Role.TENANT and user.property == post.property:
        can_view = True
    elif user.role == User.Role.EMPLOYEE and user.property == post.property:
        can_view = True
    elif user.role == User.Role.LANDLORD and user.company == post.property.company:
        can_view = True
    elif user.role == User.Role.SUPERUSER:
        can_view = True
    
    if not can_view:
        return HttpResponseForbidden("You don't have permission to view this post.")
    
    # Check if user can edit/moderate this post
    can_edit = post.can_be_edited_by(user)
    can_moderate = post.can_be_moderated_by(user)
    
    context = {
        'post': post,
        'can_edit': can_edit,
        'can_moderate': can_moderate,
    }
    return render(request, 'communication/post_detail.html', context)


@login_required
def edit_community_post(request, post_id):
    """Edit a community board post"""
    user = request.user
    post = get_object_or_404(CommunityPost, id=post_id)
    
    # Check permissions
    if not post.can_be_edited_by(user):
        django_messages.error(request, 'You do not have permission to edit this post.')
        return redirect('communication:community_post_detail', post_id=post.id)
    
    if request.method == 'POST':
        form = CommunityPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            
            # Handle new file attachments
            files = request.FILES.getlist('attachments')
            for file in files:
                CommunityPostAttachment.objects.create(
                    post=post,
                    file=file,
                    filename=file.name,
                    file_size=file.size,
                    content_type=file.content_type
                )
            
            django_messages.success(request, 'Post updated successfully.')
            return redirect('communication:community_post_detail', post_id=post.id)
    else:
        form = CommunityPostForm(instance=post)
    
    context = {
        'form': form,
        'post': post,
    }
    return render(request, 'communication/edit_post.html', context)


@login_required
def delete_community_post(request, post_id):
    """Delete/hide a community board post"""
    user = request.user
    post = get_object_or_404(CommunityPost, id=post_id)
    
    # Check permissions
    if not post.can_be_moderated_by(user):
        django_messages.error(request, 'You do not have permission to delete this post.')
        return redirect('communication:community_post_detail', post_id=post.id)
    
    if request.method == 'POST':
        post.status = CommunityPost.PostStatus.HIDDEN
        post.save()
        django_messages.success(request, 'Post has been hidden.')
        return redirect('communication:community_board')
    
    context = {
        'post': post,
    }
    return render(request, 'communication/delete_post.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read and redirect to its target URL"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    
    # Mark as read
    notification.is_read = True
    notification.save()
    
    # Redirect to the target URL if available
    if notification.link_url:
        return redirect(notification.link_url)
    else:
        return redirect('core:dashboard_redirect')


@login_required 
def notification_list(request):
    """List all notifications for the current user"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_notifications': notifications.count(),
        'unread_count': notifications.filter(is_read=False).count(),
    }
    return render(request, 'communication/notification_list.html', context)


@require_POST
@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    updated_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({
        'success': True,
        'message': f'Marked {updated_count} notifications as read'
    })
