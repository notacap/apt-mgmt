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
- **communication/**: Messaging, notifications, and community board system (completed)
- **documents/**: Document management with role-based access (completed)
- **maintenance/**: Comprehensive maintenance request workflow with invoice management (completed)
- **events/**: Calendar system with event management and work schedules (completed)
- **financials/**: Rent payment and financial tracking (completed)

### Key Models and Relationships
- **User** (users/models.py): Custom user with roles (SUPERUSER, LANDLORD, EMPLOYEE, TENANT)
- **Company** (properties/models.py): Top-level organization entity
- **Property** (properties/models.py): Properties owned by companies
- **ApartmentUnit** (properties/models.py): Individual units within properties
- **Invitation** (users/models.py): Invitation system for user onboarding
- **Document** (documents/models.py): Document management with role-based access control
- **MaintenanceRequest** (maintenance/models.py): Complete maintenance workflow with status tracking, photos, and invoice-based cost management
- **MaintenanceInvoice** (maintenance/models.py): Invoice management with documents integration for financial tracking
- **MessageThread** (communication/models.py): Direct messaging system with thread-based conversations
- **Message** (communication/models.py): Individual messages with file attachments and read status tracking
- **Notification** (communication/models.py): Enhanced notification system with dynamic updates and real-time UI interactions
- **CommunityPost** (communication/models.py): Property-specific community board with posts, events, and moderation
- **CalendarEvent** (events/models.py): Calendar system with event management, assignment, and maintenance integration
- **WorkSchedule** (events/models.py): Employee work schedule management with recurring patterns
- **PaymentSchedule** (financials/models.py): Recurring rent payment schedules for tenants with frequency and amount tracking
- **RentPayment** (financials/models.py): Individual payment records with status tracking and audit trail
- **ExpenseRecord** (financials/models.py): Property expense management with categorization and maintenance integration
- **PaymentReceipt** (financials/models.py): Receipt generation and tracking for processed payments

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
- **Phase 6 Complete**: Communication features including:
  - Direct messaging system with threaded conversations and file attachments
  - Role-based recipient selection (tenants ↔ employees/landlords)
  - Property-specific community board with posts, events, and announcements
  - Author-only editing with role-based moderation capabilities
  - Inline image display and downloadable file attachments
  - Integrated notification system for new messages
- **Notification System Enhanced**: Comprehensive notification system including:
  - Dynamic notification system for document assignments and sharing
  - Smart notification dropdown showing only unread notifications (max 5)
  - Real-time UI updates with AJAX-based notification interactions
  - Automatic notification removal from dropdown when clicked
  - Full notification list view with pagination and mark-all-read functionality
  - Context processor providing notification data to all templates
  - Visual distinction between read and unread notifications
  - Automatic notifications for tenant document uploads to managers
- **Phase 7 Complete**: Calendar system including:
  - Multi-view calendar interface (month, week, day) with responsive design
  - Role-based event management with CRUD operations for landlords/employees
  - Visual multi-day event spanning with color-coded event types
  - Employee work schedule management system
  - Maintenance request integration with automatic calendar event creation
  - Advanced filtering capabilities and timezone handling
  - Event notifications and dashboard integration
- **Phase 8 Complete**: Financial features including:
  - Comprehensive payment scheduling system for landlords/employees
  - Tenant payment interface with status tracking and history
  - Payment processing workflow with automatic status updates
  - Multi-status payment tracking (Pending, Paid, Overdue, Partial, Failed)
  - Advanced filtering and search capabilities for payment history
  - Role-based access control ensuring tenant data isolation
  - Notification system integration for payment events
  - Dashboard integration with financial navigation menus
- **Ready for Phase 9**: Detailed views and expanded functionality

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
- **Secure file handling**: UUID-based filenames for uploaded documents, photos, and message attachments
- **Role-based messaging permissions**: Property-specific communication controls with proper user isolation
- **Content moderation system**: Author-only editing with landlord/employee moderation capabilities
- DEBUG=True in development (change for production)