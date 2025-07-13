from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Document, DocumentCategory, DocumentShare
from .forms import DocumentUploadForm, DocumentShareForm, DocumentFilterForm
from communication.models import Notification
from properties.models import Property, ApartmentUnit
import mimetypes

User = get_user_model()

@login_required
def document_list(request):
    """List documents accessible to the current user"""
    # Get base queryset of documents user can access
    if request.user.role == 'SUPERUSER' or request.user.is_superuser:
        documents = Document.objects.filter(is_active=True)
    elif request.user.company:
        documents = Document.objects.filter(
            company=request.user.company,
            is_active=True
        )
    else:
        # User has no company - show empty queryset
        documents = Document.objects.none()
    
    # Apply filters
    filter_form = DocumentFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data['category']:
            documents = documents.filter(category=filter_form.cleaned_data['category'])
        
        if filter_form.cleaned_data['access_level']:
            documents = documents.filter(access_level=filter_form.cleaned_data['access_level'])
        
        if filter_form.cleaned_data['search']:
            search_term = filter_form.cleaned_data['search']
            documents = documents.filter(
                Q(title__icontains=search_term) |
                Q(description__icontains=search_term) |
                Q(original_filename__icontains=search_term)
            )
    
    # Filter by actual access permissions
    accessible_documents = [doc for doc in documents if doc.is_accessible_by_user(request.user)]
    
    # Pagination
    paginator = Paginator(accessible_documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_documents': len(accessible_documents),
    }
    return render(request, 'documents/list.html', context)

@login_required
def document_upload(request):
    """Upload a new document"""
    # Check if user has a company
    if not request.user.company and not (request.user.role == 'SUPERUSER' or request.user.is_superuser):
        messages.error(request, 'You must be assigned to a company to upload documents.')
        return redirect('documents:list')
    
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            document.company = request.user.company
            
            # Special handling for tenant uploads
            if request.user.role == 'TENANT':
                document.access_level = Document.AccessLevel.PRIVATE
                document.property = None
                document.unit = None
                # Auto-assign access to landlords and employees in the company
                document.save()
                # Add landlords and employees to allowed users
                company_managers = User.objects.filter(
                    company=request.user.company,
                    role__in=['LANDLORD', 'EMPLOYEE']
                )
                document.allowed_users.set(company_managers)
            else:
                # Handle access level logic for landlords/employees
                if document.access_level == Document.AccessLevel.COMPANY:
                    document.property = None
                    document.unit = None
                elif document.access_level == Document.AccessLevel.PROPERTY:
                    document.unit = None
                
                document.save()
                form.save_m2m()  # Save many-to-many relationships
            
            messages.success(request, f'Document "{document.title}" uploaded successfully!')
            return redirect('documents:list')
    else:
        form = DocumentUploadForm(user=request.user)
    
    return render(request, 'documents/upload.html', {'form': form})

@login_required
def document_detail(request, document_id):
    """View document details"""
    document = get_object_or_404(Document, id=document_id, is_active=True)
    
    if not document.is_accessible_by_user(request.user):
        raise Http404("Document not found")
    
    # Get sharing history
    shares = DocumentShare.objects.filter(document=document).order_by('-created_at')
    
    context = {
        'document': document,
        'shares': shares,
        'can_share': request.user.company == document.company,
    }
    return render(request, 'documents/detail.html', context)

@login_required
def document_download(request, document_id):
    """Download a document"""
    document = get_object_or_404(Document, id=document_id, is_active=True)
    
    if not document.is_accessible_by_user(request.user):
        raise Http404("Document not found")
    
    try:
        file_path = document.file.path
        with open(file_path, 'rb') as f:
            content_type, _ = mimetypes.guess_type(file_path)
            response = HttpResponse(f.read(), content_type=content_type or 'application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{document.original_filename}"'
            return response
    except FileNotFoundError:
        messages.error(request, 'File not found on server.')
        return redirect('documents:detail', document_id=document.id)

@login_required
def document_share(request, document_id):
    """Share a document with another user"""
    document = get_object_or_404(Document, id=document_id, is_active=True)
    
    if not document.is_accessible_by_user(request.user):
        raise Http404("Document not found")
    
    if request.user.company and request.user.company != document.company:
        messages.error(request, 'You can only share documents within your company.')
        return redirect('documents:detail', document_id=document.id)
    
    if request.method == 'POST':
        form = DocumentShareForm(request.POST, user=request.user)
        if form.is_valid():
            share = form.save(commit=False)
            share.document = document
            share.shared_by = request.user
            share.save()
            
            # Create notification for the recipient
            Notification.objects.create(
                recipient=share.shared_with,
                notification_type='DOCUMENT_SHARED',
                title=f'Document shared: {document.title}',
                message=f'{request.user.get_full_name() or request.user.username} shared a document with you.',
                link_url=f'/documents/{document.id}/'
            )
            
            messages.success(request, f'Document shared with {share.shared_with.get_full_name() or share.shared_with.username}!')
            return redirect('documents:detail', document_id=document.id)
    else:
        form = DocumentShareForm(user=request.user)
    
    return render(request, 'documents/share.html', {'form': form, 'document': document})

@login_required
def document_delete(request, document_id):
    """Soft delete a document"""
    document = get_object_or_404(Document, id=document_id, is_active=True)
    
    # Only the uploader or superuser can delete
    if request.user != document.uploaded_by and request.user.role != 'SUPERUSER':
        messages.error(request, 'You do not have permission to delete this document.')
        return redirect('documents:detail', document_id=document.id)
    
    if request.method == 'POST':
        document.is_active = False
        document.save()
        messages.success(request, f'Document "{document.title}" deleted successfully!')
        return redirect('documents:list')
    
    return render(request, 'documents/delete_confirm.html', {'document': document})

@login_required
def category_list(request):
    """List document categories"""
    categories = DocumentCategory.objects.all().order_by('name')
    return render(request, 'documents/categories.html', {'categories': categories})

@login_required
def shared_documents(request):
    """List documents shared with the current user"""
    shares = DocumentShare.objects.filter(
        shared_with=request.user
    ).select_related('document', 'shared_by').order_by('-created_at')
    
    # Mark as read when viewed
    shares.filter(is_read=False).update(is_read=True)
    
    context = {
        'shares': shares,
    }
    return render(request, 'documents/shared.html', context)

@login_required
def get_units_for_property(request, property_id):
    """API endpoint to get units for a specific property"""
    try:
        property_obj = get_object_or_404(Property, id=property_id)
        
        # Check if user has access to this property
        if request.user.company != property_obj.company and not (request.user.role == 'SUPERUSER' or request.user.is_superuser):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        units = ApartmentUnit.objects.filter(property=property_obj).order_by('unit_number')
        units_data = [
            {'id': unit.id, 'unit_number': unit.unit_number}
            for unit in units
        ]
        
        return JsonResponse({'units': units_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
