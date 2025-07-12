  # Apartment Management Platform - Project Specification

## Project Overview

A comprehensive web-based platform designed for apartment management companies to streamline operations between landlords/owners, employees, and tenants. The platform features role-based dashboards with unified login, document management, maintenance tracking, rent collection, and communication tools.

## Technical Stack

- **Backend**: Django
- **Frontend**: HTMX, Alpine.js
- **Styling**: Tailwind CSS (CDN for development, build process for production)
- **UI Requirements**: Clean, simple, modern design with light/dark mode toggle

## User Roles & Permissions

### 1. Superuser (System Administrator)
- Full system access
- No dedicated dashboard required
- Can access all pages and functionality
- Manages landlord accounts and company structure

### 2. Landlord (Property Owner)
- Full control over their properties, employees, and tenants
- Access to comprehensive metrics and management tools
- Document and financial management capabilities

### 3. Employee (Property Staff)
- Limited administrative access
- Maintenance management
- Communication with tenants and landlords
- Document access (restricted)

### 4. Tenant (Resident)
- Self-service portal for rent payment and maintenance requests
- Communication with management
- Document upload and viewing capabilities

## Authentication & Authorization

- Single login page for all user types
- Role-based redirection post-login:
  - Landlords → Landlord Dashboard
  - Employees → Employee Dashboard
  - Tenants → Tenant Dashboard
  - Superuser → Admin access (no specific dashboard)

## Common Features (All Dashboards)

### 1. Direct Messaging System
- User-to-user messaging based on role permissions
- Document attachment capabilities
- Message history and search

### 2. Community Board
- Public posting area for announcements and discussions
- Role-based posting and deletion permissions
- Moderation capabilities for landlords and employees

### 3. Calendar System
- Event creation and viewing
- Maintenance scheduling integration
- Work schedule display for employees

### 4. Notification System
- Social media-style notification badges
- Real-time updates for relevant activities
- Examples:
  - Landlords: New maintenance requests, rent payments
  - Tenants: Maintenance status updates, new messages
  - Employees: Work assignments, schedule changes

## Role-Specific Features

### Superuser Capabilities

1. **Company Management**
   - Add new landlord accounts
   - Create and configure management companies
   - Set up properties under company ownership

2. **Property Configuration**
   - Add apartment units to properties
   - Configure property details

### Landlord Dashboard

1. **Multi-Property Support**
   - Property selector for filtered views
   - Default view shows aggregated data across all properties

2. **Metrics Cards (Clickable for Details)**
   - Monthly rent income
   - Monthly expenses
   - Monthly revenue
   - Maintenance request overview
   - Payment status overview (on-time vs. late)
   - Occupancy rate
   - Lease expiration alerts (30, 60, 90 days)

3. **Tenant Management**
   - Simplified tenant addition process:
     - Name and email
     - Lease details (start date, duration)
     - Apartment assignment
     - Rent amount
     - Automated invitation email
   - Tenant list with editing capabilities

4. **Employee Management**
   - Add/edit employee accounts
   - Work schedule management
   - Employee list view

5. **Document Management**
   - Upload capabilities (leases, invoices, etc.)
   - Document sharing with specific users or groups
   - Access control:
     - Individual employee/tenant
     - All employees
     - All tenants
     - Everyone

6. **Maintenance Management**
   - Review all maintenance requests
   - Status updates
   - Scheduling and worker assignment
   - Cost tracking and invoice uploads

7. **Communication**
   - Direct messaging with document sharing
   - Community board moderation
   - Calendar event creation

### Employee Dashboard

1. **Maintenance Management**
   - Same permissions as landlord for maintenance requests
   - View assigned work orders
   - Update request status

2. **Document Management**
   - Upload documents for tenants
   - View documents associated with:
     - All tenants
     - All employees
     - Everyone
   - Cannot view other employees' private documents

3. **Communication**
   - Direct messaging to landlords and tenants
   - Community board posting and moderation
   - Document sharing in messages

4. **Calendar**
   - View and create events
   - View work schedule
   - See maintenance appointments

### Tenant Dashboard

1. **Rent Management**
   - Pay rent (immediate or scheduled)
   - View payment history
   - View lease details (rent amount, end date)

2. **Maintenance Requests**
   - Create new requests with photo attachments
   - Select urgency/category
   - Modify own requests until completed
   - View status updates
   - View scheduled maintenance for their unit

3. **Document Management**
   - Upload personal documents
   - View documents shared by management
   - Download capabilities

4. **Communication**
   - Direct message landlord or all employees
   - Post to community board
   - Delete own community posts
   - Attach documents to messages

5. **Calendar**
   - View events
   - View scheduled maintenance for their unit

## Database Structure Considerations

- Multi-tenancy support for multiple management companies
- Property hierarchy: Company → Properties → Units
- User role assignment and permissions
- Document storage with access control
- Maintenance request workflow states
- Payment tracking and history
- Calendar events with visibility rules

## Security Requirements

- Role-based access control (RBAC)
- Secure document storage
- Encrypted payment processing
- Audit trail for sensitive actions
- Session management and timeout

## UI/UX Requirements

- Responsive design for desktop and mobile
- Intuitive navigation with role-appropriate menus
- Light/dark mode toggle
- Consistent design language across all dashboards
- Loading states and error handling
- Accessibility compliance

---

# Developer To-Do List

## Phase 1: Foundation Setup

- [ ] Initialize Django project with proper structure
- [ ] Set up development environment with HTMX, Alpine.js, and Tailwind CDN
- [ ] Configure database models for multi-tenancy support
- [ ] Implement user authentication system with role-based permissions
- [ ] Create base templates with light/dark mode toggle
- [ ] Set up URL routing for different user roles

## Phase 2: User Management

- [ ] Build superuser admin interface
- [ ] Create landlord account creation and company setup
- [ ] Implement property and unit management for superusers
- [ ] Build user invitation system with email integration
- [ ] Create profile management for all user types
- [ ] Implement role-based dashboard redirection

## Phase 3: Core Dashboard Features

- [ ] Build notification system with badge display
- [ ] Create reusable metric card components
- [ ] Implement landlord dashboard with all metric cards
- [ ] Add property selector with filtered views
- [ ] Create employee dashboard layout
- [ ] Build tenant dashboard structure

## Phase 4: Document Management

- [ ] Set up file upload system with secure storage
- [ ] Implement document access control logic
- [ ] Create document sharing interface
- [ ] Build document viewing/downloading system
- [ ] Add document association with users/groups
- [ ] Implement document management UI for each role

## Phase 5: Maintenance System

- [ ] Create maintenance request model and workflow
- [ ] Build tenant maintenance request creation form
- [ ] Implement photo upload for maintenance requests
- [ ] Create maintenance management interface for landlords/employees
- [ ] Add status tracking and updates
- [ ] Build maintenance scheduling system
- [ ] Implement cost tracking and invoice uploads

## Phase 6: Communication Features

- [ ] Build direct messaging system
- [ ] Implement message recipient selection based on roles
- [ ] Add document attachment to messages
- [ ] Create community board with posting capabilities
- [ ] Implement role-based moderation features
- [ ] Add message notifications

## Phase 7: Calendar System

- [ ] Create calendar event model
- [ ] Build calendar UI with month/week/day views
- [ ] Implement event creation for authorized users
- [ ] Add maintenance request integration
- [ ] Create work schedule management for employees
- [ ] Implement calendar filtering by user role

## Phase 8: Financial Features

- [ ] Build rent payment interface for tenants
- [ ] Implement payment scheduling system
- [ ] Create payment history tracking
- [ ] Add payment notification system
- [ ] Build financial reporting for landlords
- [ ] Implement expense tracking

## Phase 9: Detailed Views

- [ ] Create expanded views for metric cards
- [ ] Build maintenance request list with filters
- [ ] Implement lease expiration report
- [ ] Create tenant and employee list views
- [ ] Add search and filter capabilities

## Phase 10: Testing & Optimization

- [ ] Write comprehensive test suite
- [ ] Perform security audit
- [ ] Optimize database queries
- [ ] Implement caching where appropriate
- [ ] Test responsive design across devices
- [ ] Conduct accessibility testing

## Phase 11: Production Preparation

- [ ] Set up Tailwind build process
- [ ] Configure production settings
- [ ] Set up error logging and monitoring
- [ ] Create deployment scripts
- [ ] Prepare documentation
- [ ] Set up backup systems

## Phase 12: Polish & Launch

- [ ] UI/UX refinements based on testing
- [ ] Performance optimization
- [ ] Final security review
- [ ] User acceptance testing
- [ ] Create user guides for each role
- [ ] Deploy to production

