from django.db import models
from django.contrib.auth import get_user_model
from properties.models import Company, Property, ApartmentUnit
import os
import uuid

User = get_user_model()

def document_upload_path(instance, filename):
    """Generate upload path for documents with UUID prefix for security"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"documents/{instance.company.id}/{filename}"

class DocumentCategory(models.Model):
    """Categories for organizing documents"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Document Categories"
    
    def __str__(self):
        return self.name

class Document(models.Model):
    """Main document model with role-based access control"""
    
    class AccessLevel(models.TextChoices):
        COMPANY = "COMPANY", "Company-wide"
        PROPERTY = "PROPERTY", "Property-specific"
        UNIT = "UNIT", "Unit-specific"
        PRIVATE = "PRIVATE", "Private (specific users)"
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    file_type = models.CharField(max_length=100)
    
    # Organization
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="documents")
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="documents", null=True, blank=True)
    unit = models.ForeignKey(ApartmentUnit, on_delete=models.CASCADE, related_name="documents", null=True, blank=True)
    
    # Access control
    access_level = models.CharField(max_length=20, choices=AccessLevel.choices, default=AccessLevel.COMPANY)
    allowed_users = models.ManyToManyField(User, related_name="accessible_documents", blank=True)
    allowed_roles = models.JSONField(default=list, blank=True)  # List of role strings
    
    # Metadata
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploaded_documents")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'access_level']),
            models.Index(fields=['property']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.company.name})"
    
    def save(self, *args, **kwargs):
        if self.file and not self.pk:  # Only on first save (new upload)
            import mimetypes
            
            # Set original filename
            self.original_filename = getattr(self.file, 'name', 'unknown_file')
            
            # Set file size
            try:
                self.file_size = self.file.size
            except (AttributeError, OSError):
                self.file_size = 0
            
            # Set file type with multiple fallbacks
            self.file_type = 'application/octet-stream'  # Default
            
            # Try to get content type from the uploaded file
            if hasattr(self.file, 'content_type') and self.file.content_type:
                self.file_type = self.file.content_type
            elif hasattr(self.file, 'file') and hasattr(self.file.file, 'content_type') and self.file.file.content_type:
                self.file_type = self.file.file.content_type
            else:
                # Guess from filename
                content_type, _ = mimetypes.guess_type(self.original_filename)
                if content_type:
                    self.file_type = content_type
        
        super().save(*args, **kwargs)
    
    def get_file_extension(self):
        """Get file extension for display purposes"""
        return os.path.splitext(self.original_filename)[1].lower()
    
    def is_accessible_by_user(self, user):
        """Check if a user can access this document"""
        # Superusers can access all documents
        if user.role == 'SUPERUSER' or user.is_superuser:
            return True
        
        # Users can always access documents they uploaded themselves
        if self.uploaded_by == user:
            return True
        
        # Users must be in the same company
        if user.company != self.company:
            return False
        
        # Check specific user permissions
        if self.allowed_users.filter(id=user.id).exists():
            return True
        
        # Check role-based permissions
        if user.role in self.allowed_roles:
            return True
        
        # Check access level permissions
        if self.access_level == self.AccessLevel.COMPANY:
            return True
        elif self.access_level == self.AccessLevel.PROPERTY:
            return user.property == self.property
        elif self.access_level == self.AccessLevel.UNIT:
            return user.property == self.property and hasattr(user, 'unit') and user.unit == self.unit
        
        return False

class DocumentShare(models.Model):
    """Track document sharing between users"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="shares")
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shared_documents")
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_documents")
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['document', 'shared_by', 'shared_with']
    
    def __str__(self):
        return f"{self.shared_by.username} shared {self.document.title} with {self.shared_with.username}"
