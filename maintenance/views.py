from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from users.models import User
from documents.models import Document, DocumentCategory
from .models import MaintenanceRequest, MaintenancePhoto, MaintenanceUpdate, MaintenanceCategory, MaintenanceInvoice
from .forms import (
    MaintenanceRequestForm, MaintenancePhotoFormSet, MaintenanceUpdateForm,
    MaintenanceStatusUpdateForm, MaintenanceInvoiceForm
)


@login_required
def maintenance_list(request):
    """List maintenance requests based on user role"""
    user = request.user
    
    # Filter requests based on user role and permissions
    if user.role == User.Role.TENANT:
        requests = MaintenanceRequest.objects.filter(tenant=user)
    elif user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        requests = MaintenanceRequest.objects.filter(property__company=user.company)
        if user.property:
            requests = requests.filter(property=user.property)
    else:  # Superuser
        requests = MaintenanceRequest.objects.all()
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        requests = requests.filter(status=status)
    
    # Filter by priority if provided
    priority = request.GET.get('priority')
    if priority:
        requests = requests.filter(priority=priority)
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        requests = requests.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(tenant__username__icontains=search)
        )
    
    # Order by creation date (newest first)
    requests = requests.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_choices': MaintenanceRequest.Status.choices,
        'priority_choices': MaintenanceRequest.Priority.choices,
        'current_status': status,
        'current_priority': priority,
        'search_query': search,
    }
    
    return render(request, 'maintenance/list.html', context)


@login_required
def maintenance_detail(request, pk):
    """View maintenance request details"""
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    user = request.user
    
    # Check permissions
    if user.role == User.Role.TENANT and maintenance_request.tenant != user:
        messages.error(request, "You don't have permission to view this request.")
        return redirect('maintenance:list')
    elif user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        if maintenance_request.property.company != user.company:
            messages.error(request, "You don't have permission to view this request.")
            return redirect('maintenance:list')
        if user.property and maintenance_request.property != user.property:
            messages.error(request, "You don't have permission to view this request.")
            return redirect('maintenance:list')
    
    # Get all updates for this request
    updates = maintenance_request.updates.all().order_by('-created_at')
    
    # Forms for adding updates (only for landlords/employees)
    update_form = None
    status_form = None
    invoice_form = None
    
    if user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        update_form = MaintenanceUpdateForm()
        status_form = MaintenanceStatusUpdateForm(instance=maintenance_request, user=user)
        invoice_form = MaintenanceInvoiceForm()
    
    context = {
        'maintenance_request': maintenance_request,
        'updates': updates,
        'update_form': update_form,
        'status_form': status_form,
        'invoice_form': invoice_form,
        'can_manage': user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER],
    }
    
    return render(request, 'maintenance/detail.html', context)


@login_required
def maintenance_create(request):
    """Create a new maintenance request (tenants only)"""
    if request.user.role != User.Role.TENANT:
        messages.error(request, "Only tenants can create maintenance requests.")
        return redirect('maintenance:list')
    
    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST, user=request.user)
        photo_formset = MaintenancePhotoFormSet(request.POST, request.FILES)
        
        if form.is_valid() and photo_formset.is_valid():
            # Create the maintenance request
            maintenance_request = form.save(commit=False)
            maintenance_request.tenant = request.user
            maintenance_request.property = request.user.property
            maintenance_request.save()
            
            # Save photos
            for photo_form in photo_formset:
                if photo_form.cleaned_data and photo_form.cleaned_data.get('photo'):
                    photo = photo_form.save(commit=False)
                    photo.maintenance_request = maintenance_request
                    photo.uploaded_by = request.user
                    photo.save()
            
            # Create initial update
            MaintenanceUpdate.objects.create(
                maintenance_request=maintenance_request,
                update_type=MaintenanceUpdate.UpdateType.STATUS_CHANGE,
                message=f"Maintenance request submitted by {request.user.get_full_name() or request.user.username}",
                created_by=request.user,
                new_status=MaintenanceRequest.Status.SUBMITTED
            )
            
            messages.success(request, "Your maintenance request has been submitted successfully.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
    else:
        form = MaintenanceRequestForm(user=request.user)
        photo_formset = MaintenancePhotoFormSet()
    
    context = {
        'form': form,
        'photo_formset': photo_formset,
    }
    
    return render(request, 'maintenance/create.html', context)


@login_required
def maintenance_update_status(request, pk):
    """Update maintenance request status (landlords/employees only)"""
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        messages.error(request, "You don't have permission to update maintenance requests.")
        return redirect('maintenance:detail', pk=pk)
    
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    
    # Check permissions
    if request.user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        if maintenance_request.property.company != request.user.company:
            messages.error(request, "You don't have permission to update this request.")
            return redirect('maintenance:detail', pk=pk)
    
    if request.method == 'POST':
        old_status = maintenance_request.status
        form = MaintenanceStatusUpdateForm(request.POST, instance=maintenance_request, user=request.user)
        
        if form.is_valid():
            maintenance_request = form.save()
            
            # Create update record if status changed
            if old_status != maintenance_request.status:
                MaintenanceUpdate.objects.create(
                    maintenance_request=maintenance_request,
                    update_type=MaintenanceUpdate.UpdateType.STATUS_CHANGE,
                    message=f"Status changed from {old_status} to {maintenance_request.status}",
                    created_by=request.user,
                    old_status=old_status,
                    new_status=maintenance_request.status
                )
                
                # Create calendar event if status changed to SCHEDULED and scheduled_date is set
                if (maintenance_request.status == MaintenanceRequest.Status.SCHEDULED and 
                    maintenance_request.scheduled_date):
                    from events.models import CalendarEvent
                    from django.utils import timezone
                    
                    # Check if calendar event already exists for this maintenance request
                    existing_event = CalendarEvent.objects.filter(
                        maintenance_request=maintenance_request
                    ).first()
                    
                    if not existing_event:
                        # Create calendar event
                        calendar_event = CalendarEvent.objects.create(
                            title=f"Maintenance: {maintenance_request.title}",
                            description=f"Scheduled maintenance for {maintenance_request.property}" + 
                                      (f" - {maintenance_request.apartment_unit}" if maintenance_request.apartment_unit else "") +
                                      f"\n\nDescription: {maintenance_request.description}" +
                                      (f"\nLocation: {maintenance_request.location_details}" if maintenance_request.location_details else ""),
                            event_type=CalendarEvent.EventType.MAINTENANCE,
                            priority=CalendarEvent.Priority.HIGH if maintenance_request.priority == MaintenanceRequest.Priority.EMERGENCY 
                                   else CalendarEvent.Priority.MEDIUM,
                            start_datetime=maintenance_request.scheduled_date,
                            end_datetime=maintenance_request.estimated_completion or 
                                       (maintenance_request.scheduled_date + timezone.timedelta(hours=2)),
                            property=maintenance_request.property,
                            apartment_unit=maintenance_request.apartment_unit,
                            location_details=maintenance_request.location_details,
                            created_by=request.user,
                            maintenance_request=maintenance_request,
                            is_private=False  # Visible to landlords, employees, and requesting tenant
                        )
                        
                        # Assign the tenant who created the maintenance request to the calendar event
                        calendar_event.assigned_to.add(maintenance_request.tenant)
                        
                        # Also assign the maintenance worker if one is assigned
                        if maintenance_request.assigned_to:
                            calendar_event.assigned_to.add(maintenance_request.assigned_to)
                
                # Update completed_at timestamp if marked as completed
                if maintenance_request.status == MaintenanceRequest.Status.COMPLETED:
                    from django.utils import timezone
                    maintenance_request.completed_at = timezone.now()
                    maintenance_request.save()
            
            messages.success(request, "Maintenance request updated successfully.")
            return redirect('maintenance:detail', pk=pk)
    
    return redirect('maintenance:detail', pk=pk)


@login_required
def maintenance_add_update(request, pk):
    """Add an update to a maintenance request"""
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        messages.error(request, "You don't have permission to add updates.")
        return redirect('maintenance:detail', pk=pk)
    
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    
    if request.method == 'POST':
        form = MaintenanceUpdateForm(request.POST)
        
        if form.is_valid():
            update = form.save(commit=False)
            update.maintenance_request = maintenance_request
            update.created_by = request.user
            update.save()
            
            messages.success(request, "Update added successfully.")
            return redirect('maintenance:detail', pk=pk)
    
    return redirect('maintenance:detail', pk=pk)


@login_required
def maintenance_add_invoice(request, pk):
    """Add an invoice to a maintenance request"""
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        messages.error(request, "You don't have permission to add invoices.")
        return redirect('maintenance:detail', pk=pk)
    
    maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)
    
    if request.method == 'POST':
        form = MaintenanceInvoiceForm(request.POST, request.FILES)
        
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.maintenance_request = maintenance_request
            invoice.uploaded_by = request.user
            invoice.save()
            
            # Create document record in documents module if invoice file was uploaded
            if invoice.invoice_file:
                try:
                    # Get the Maintenance Records category
                    maintenance_category = DocumentCategory.objects.get(name="Maintenance Records")
                    
                    # Create document record
                    document = Document.objects.create(
                        title=f"Maintenance Invoice - {invoice.vendor_name} (#{invoice.invoice_number})",
                        description=f"Invoice for maintenance request: {maintenance_request.title}. Amount: ${invoice.amount}",
                        file=invoice.invoice_file,
                        category=maintenance_category,
                        company=maintenance_request.property.company,
                        property=maintenance_request.property,
                        unit=maintenance_request.apartment_unit,
                        access_level=Document.AccessLevel.PROPERTY,
                        allowed_roles=["LANDLORD", "EMPLOYEE"],  # Only landlords and employees can view
                        uploaded_by=request.user
                    )
                    
                    # Link the document to the invoice
                    invoice.document = document
                    invoice.save()
                    
                except DocumentCategory.DoesNotExist:
                    messages.warning(request, "Invoice uploaded but document category 'Maintenance Records' not found.")
                except Exception as e:
                    messages.warning(request, f"Invoice uploaded but couldn't create document record: {str(e)}")
            
            # Create update record
            MaintenanceUpdate.objects.create(
                maintenance_request=maintenance_request,
                update_type=MaintenanceUpdate.UpdateType.NOTE,
                message=f"Invoice added: {invoice.vendor_name} - ${invoice.amount}",
                created_by=request.user
            )
            
            messages.success(request, "Invoice added successfully and made available in documents.")
            return redirect('maintenance:detail', pk=pk)
    
    return redirect('maintenance:detail', pk=pk)


@login_required
def maintenance_edit_invoice(request, invoice_id):
    """Edit an existing maintenance invoice"""
    invoice = get_object_or_404(MaintenanceInvoice, id=invoice_id)
    maintenance_request = invoice.maintenance_request
    
    # Check permissions
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        messages.error(request, "You don't have permission to edit invoices.")
        return redirect('maintenance:detail', pk=maintenance_request.pk)
    
    # Check company/property access
    if request.user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        if maintenance_request.property.company != request.user.company:
            messages.error(request, "You don't have permission to edit this invoice.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
        if request.user.property and maintenance_request.property != request.user.property:
            messages.error(request, "You don't have permission to edit this invoice.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
    
    if request.method == 'POST':
        form = MaintenanceInvoiceForm(request.POST, request.FILES, instance=invoice)
        
        if form.is_valid():
            # Check if file was updated
            file_updated = 'invoice_file' in request.FILES
            
            invoice = form.save(commit=False)
            invoice.save()
            
            # Update document record if it exists
            if invoice.document:
                document = invoice.document
                document.title = f"Maintenance Invoice - {invoice.vendor_name} (#{invoice.invoice_number})"
                document.description = f"Invoice for maintenance request: {maintenance_request.title}. Amount: ${invoice.amount}"
                
                # Update file if new one was uploaded
                if file_updated:
                    document.file = invoice.invoice_file
                
                document.save()
            elif file_updated and invoice.invoice_file:
                # Create new document record if file was added and none existed
                try:
                    maintenance_category = DocumentCategory.objects.get(name="Maintenance Records")
                    
                    document = Document.objects.create(
                        title=f"Maintenance Invoice - {invoice.vendor_name} (#{invoice.invoice_number})",
                        description=f"Invoice for maintenance request: {maintenance_request.title}. Amount: ${invoice.amount}",
                        file=invoice.invoice_file,
                        category=maintenance_category,
                        company=maintenance_request.property.company,
                        property=maintenance_request.property,
                        unit=maintenance_request.apartment_unit,
                        access_level=Document.AccessLevel.PROPERTY,
                        allowed_roles=["LANDLORD", "EMPLOYEE"],
                        uploaded_by=request.user
                    )
                    
                    invoice.document = document
                    invoice.save()
                    
                except DocumentCategory.DoesNotExist:
                    messages.warning(request, "Invoice updated but document category 'Maintenance Records' not found.")
                except Exception as e:
                    messages.warning(request, f"Invoice updated but couldn't create document record: {str(e)}")
            
            # Create update record
            MaintenanceUpdate.objects.create(
                maintenance_request=maintenance_request,
                update_type=MaintenanceUpdate.UpdateType.NOTE,
                message=f"Invoice updated: {invoice.vendor_name} - ${invoice.amount}",
                created_by=request.user
            )
            
            messages.success(request, "Invoice updated successfully.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
    else:
        form = MaintenanceInvoiceForm(instance=invoice)
    
    context = {
        'form': form,
        'invoice': invoice,
        'maintenance_request': maintenance_request,
    }
    
    return render(request, 'maintenance/edit_invoice.html', context)


@login_required
def maintenance_delete_invoice(request, invoice_id):
    """Delete a maintenance invoice"""
    invoice = get_object_or_404(MaintenanceInvoice, id=invoice_id)
    maintenance_request = invoice.maintenance_request
    
    # Check permissions
    if request.user.role not in [User.Role.LANDLORD, User.Role.EMPLOYEE, User.Role.SUPERUSER]:
        messages.error(request, "You don't have permission to delete invoices.")
        return redirect('maintenance:detail', pk=maintenance_request.pk)
    
    # Check company/property access
    if request.user.role in [User.Role.LANDLORD, User.Role.EMPLOYEE]:
        if maintenance_request.property.company != request.user.company:
            messages.error(request, "You don't have permission to delete this invoice.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
        if request.user.property and maintenance_request.property != request.user.property:
            messages.error(request, "You don't have permission to delete this invoice.")
            return redirect('maintenance:detail', pk=maintenance_request.pk)
    
    if request.method == 'POST':
        vendor_name = invoice.vendor_name
        amount = invoice.amount
        
        # Delete associated document if it exists
        if invoice.document:
            invoice.document.delete()
        
        # Delete the invoice
        invoice.delete()
        
        # Create update record
        MaintenanceUpdate.objects.create(
            maintenance_request=maintenance_request,
            update_type=MaintenanceUpdate.UpdateType.NOTE,
            message=f"Invoice deleted: {vendor_name} - ${amount}",
            created_by=request.user
        )
        
        messages.success(request, "Invoice deleted successfully.")
        return redirect('maintenance:detail', pk=maintenance_request.pk)
    
    context = {
        'invoice': invoice,
        'maintenance_request': maintenance_request,
    }
    
    return render(request, 'maintenance/delete_invoice.html', context)
