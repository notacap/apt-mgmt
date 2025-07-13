from django.contrib import admin
from .models import Document, DocumentCategory, DocumentShare

@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'access_level', 'uploaded_by', 'created_at', 'is_active']
    list_filter = ['access_level', 'company', 'is_active', 'created_at']
    search_fields = ['title', 'description', 'original_filename']
    readonly_fields = ['file_size', 'file_type', 'original_filename', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(company=request.user.company)

@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ['document', 'shared_by', 'shared_with', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['document__title', 'shared_by__username', 'shared_with__username']
