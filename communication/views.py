from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Max, Count
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from .models import MessageThread, Message, MessageAttachment, MessageReadStatus, Notification
from .forms import MessageForm, NewThreadForm
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
            # Get landlords and employees from the same company
            recipients = User.objects.filter(
                Q(role=User.Role.LANDLORD, company=user.company) |
                Q(role=User.Role.EMPLOYEE, property=user.property)
            ).exclude(id=user.id)
    
    elif user.role == User.Role.EMPLOYEE:
        # Employees can message landlords from their company and tenants from their property
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
