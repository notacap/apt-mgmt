from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from properties.models import Company, Property
from .models import Document, DocumentCategory

User = get_user_model()

class DocumentTestCase(TestCase):
    def setUp(self):
        # Create test company and property
        self.company = Company.objects.create(
            name="Test Company"
        )
        self.property = Property.objects.create(
            name="Test Property",
            address="456 Property St",
            company=self.company
        )
        
        # Create test users
        self.landlord = User.objects.create_user(
            username='testlandlord',
            email='landlord@test.com',
            password='testpass123',
            role='LANDLORD',
            company=self.company,
            property=self.property
        )
        
        self.tenant = User.objects.create_user(
            username='testtenant',
            email='tenant@test.com',
            password='testpass123',
            role='TENANT',
            company=self.company,
            property=self.property
        )
        
        # Create test category
        self.category = DocumentCategory.objects.create(
            name="Test Category",
            description="Test category description"
        )
        
        self.client = Client()

    def test_document_list_view(self):
        """Test that document list view loads correctly"""
        self.client.force_login(self.landlord)
        response = self.client.get(reverse('documents:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documents')

    def test_document_upload_view(self):
        """Test that document upload view loads correctly"""
        self.client.force_login(self.landlord)
        response = self.client.get(reverse('documents:upload'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Upload Document')

    def test_document_model_access_control(self):
        """Test document access control logic"""
        # Create test document
        test_file = SimpleUploadedFile(
            "test.txt", 
            b"test file content", 
            content_type="text/plain"
        )
        
        document = Document(
            title="Test Document",
            description="Test description",
            file=test_file,
            company=self.company,
            uploaded_by=self.landlord,
            access_level=Document.AccessLevel.COMPANY
        )
        document.save()
        
        # Test access control
        self.assertTrue(document.is_accessible_by_user(self.landlord))
        self.assertTrue(document.is_accessible_by_user(self.tenant))
        
        # Test property-specific access
        document.access_level = Document.AccessLevel.PROPERTY
        document.property = self.property
        document.save()
        
        self.assertTrue(document.is_accessible_by_user(self.landlord))
        self.assertTrue(document.is_accessible_by_user(self.tenant))

    def test_user_without_company_access(self):
        """Test that users without company get empty document list"""
        user_no_company = User.objects.create_user(
            username='nocompany',
            email='nocompany@test.com',
            password='testpass123',
            role='TENANT'
            # No company assigned
        )
        
        self.client.force_login(user_no_company)
        response = self.client.get(reverse('documents:list'))
        self.assertEqual(response.status_code, 200)
        # Should show empty state
        self.assertContains(response, 'No documents')
