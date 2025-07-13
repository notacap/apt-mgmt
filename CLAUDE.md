# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Important Rule: DO NOT TRY TO RUN THE DEVELOPMENT SERVER. I AM RUNNING IT IN THE BACKGROUND IN A SEPARATE TERMINAL. WHEN YOU TRY TO RUN IT, I NEED TO MANUALLY KILL ALL PYTHON PROCESSES.

Another Important Rule: Do not try to test newly implemented features. I will test them for you.-+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

## Development Commands

### Running the Application
```bash
python manage.py runserver
```

### Database Management
```bash
# Apply migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser

# Reset database (development only)
# Delete db.sqlite3 and run migrate
```

### Testing
```bash
# Run all tests
python manage.py test

# Run tests for specific app
python manage.py test core
python manage.py test users
```

## Project Architecture

This is a Django apartment management platform with a multi-app structure designed for scalability and separation of concerns.

### Application Structure
- **apt_mgmt_official/**: Main Django project configuration
- **core/**: Central app handling authentication, dashboards, and main views
- **users/**: Custom user model with role-based permissions and invitation system
- **properties/**: Company, Property, and ApartmentUnit models for multi-tenancy
- **communication/**: Messaging and notification system (planned)
- **documents/**: Document management with role-based access (completed)
- **maintenance/**: Comprehensive maintenance request workflow with invoice management (completed)
- **financials/**: Rent payment and financial tracking (planned)

### Key Models and Relationships
- **User** (users/models.py): Custom user with roles (SUPERUSER, LANDLORD, EMPLOYEE, TENANT)
- **Company** (properties/models.py): Top-level organization entity
- **Property** (properties/models.py): Properties owned by companies
- **ApartmentUnit** (properties/models.py): Individual units within properties
- **Invitation** (users/models.py): Invitation system for user onboarding
- **Document** (documents/models.py): Document management with role-based access control
- **MaintenanceRequest** (maintenance/models.py): Complete maintenance workflow with status tracking, photos, and invoice-based cost management
- **MaintenanceInvoice** (maintenance/models.py): Invoice management with documents integration for financial tracking

### Multi-Tenancy Design
The platform supports multiple management companies through:
- Users belong to a Company and optionally a specific Property
- Properties are owned by Companies
- Role-based permissions ensure users only access their company's data

### Authentication Flow
1. Single login page for all user types (core/urls.py:18)
2. Post-login redirection based on user role (core/views.py:88-98):
   - LANDLORD → landlord_dashboard
   - EMPLOYEE → employee_dashboard  
   - TENANT → tenant_dashboard
   - SUPERUSER → Django admin

### User Role System
- **Groups created via data migration** (users/migrations/0002_populate_groups.py)
- **Role hierarchy**: Superuser > Landlord > Employee > Tenant
- **Invitation system**: Landlords/Employees can invite users to their company/property

### Frontend Technology Stack
- **HTMX**: For dynamic interactions
- **Alpine.js**: For client-side reactivity
- **Tailwind CSS**: For styling (CDN in development)
- **Templates**: Located in core/templates/ with role-specific dashboards

### Current Development Status
- **Phase 1, 2 & 3 Complete**: Foundation setup, user management, and core dashboard features
- **Phase 4 Complete**: Document management system with secure file uploads and role-based access
- **Phase 5 Complete with Enhancements**: Comprehensive maintenance system including:
  - Full maintenance request workflow with photo uploads and status tracking
  - Complete invoice management (CRUD operations) with documents integration
  - Enhanced UI/UX with improved forms, layouts, and navigation
  - Strict role-based access control preventing tenant access to financial information
  - Photo download functionality and improved filter controls
- **Ready for Phase 6**: Communication features (messaging system)

### Important Files to Update
- **project_context.md**: Update when completing major phases
- **instructions.md**: Contains full project specification and roadmap
- **settings.py**: Uses custom AUTH_USER_MODEL = "users.User"

### Security Considerations
- Custom user model with role-based access control
- Company-level data isolation
- Invitation tokens for secure user onboarding
- **Enhanced document access control**: Fixed vulnerability where role restrictions could be bypassed by property-level access
- **Strict financial data protection**: Maintenance invoices and cost information completely hidden from tenants
- **Secure file handling**: UUID-based filenames for uploaded documents and photos
- DEBUG=True in development (change for production)