# Project Context

## Project Overview

This project is a comprehensive web-based platform for apartment management companies, designed to streamline operations between landlords/owners, employees, and tenants. The technical stack includes Django for the backend, with HTMX, Alpine.js, and Tailwind CSS for the frontend. The platform features role-based dashboards, document management, maintenance tracking, rent collection, and communication tools.

## Tech Stack

- Django
- HTMX
- Alpine.js
- Tailwind CDN
- SQLite 3

## Work Completed

**Phase 1: Foundation Setup** has been fully completed. The key accomplishments include:
- Initialized the Django project with a scalable, multi-app structure.
- Configured the frontend development environment and a base template with a light/dark mode toggle.
- Defined and migrated database models for multi-tenancy (`Company`, `Property`, `ApartmentUnit`).
- Implemented a custom user model with role-based permissions and resolved all migration conflicts.
- Set up initial URL routing for placeholder dashboards.

**Phase 2: User Management** has been fully completed. The key accomplishments include:
- Built the superuser admin interface by registering all relevant models.
- Created a system for new landlord account and company creation.
- Ensured property and unit management is available to superusers via the admin.
- Built a user invitation system with a model, form, and view.
- Implemented profile management for all user types.
- Established role-based dashboard redirection after login, including login/logout views.

**Phase 3: Core Dashboard Features** has been fully completed. The key accomplishments include:
- **Built notification system with badge display**: Created a `Notification` model in the `communication` app with notification types, recipient targeting, and badge display in the header navigation.
- **Created reusable metric card components**: Developed reusable metric card template with customizable icons, colors, and trend indicators.
- **Implemented landlord dashboard with all metric cards**: Built comprehensive landlord dashboard featuring all required metrics (rent income, expenses, revenue, maintenance requests, payment status, occupancy rate, lease expirations, vacant units) with property selector and recent activity sections.
- **Added property selector with filtered views**: Implemented property filtering dropdown in the landlord dashboard header.
- **Created employee dashboard layout**: Built employee-focused dashboard with maintenance management, schedule view, document access, and communication features.
- **Built tenant dashboard structure**: Developed tenant self-service portal with rent management, maintenance requests, document access, and messaging capabilities.

## Key Architectural Decisions & Fixes
- **Corrected User/Property Hierarchy**: The invitation system was updated to enforce the correct business logic. When a landlord or employee sends an invitation, they must now select a specific property belonging to their company. The invited user is automatically associated with both the company and the selected property upon registration.
- **Programmatic Group Permissions**: User groups ("Landlords", "Employees", "Tenants") and their associated model permissions are now created automatically via a Django data migration. This ensures a consistent and version-controlled permission setup.
- **Fixed Admin User Creation**: The Django admin for the User model was customized to display and allow editing of the custom `role` and `company` fields. This fixed a critical bug where users created via the admin were not being assigned a role, causing login redirection to fail.
- **Resolved Migration Conflicts**: A significant migration conflict (InconsistentMigrationHistory) arose after implementing the custom user model. This was resolved by resetting the `users` app migrations and rebuilding them, which required a one-time database reset and recreation of user accounts.
- **Fixed Logout Functionality**: Corrected the logout process by replacing the GET request link with a POST request form. This ensures secure and reliable user logout, preventing CSRF vulnerabilities and fixing a bug where users were not being properly logged out.

## Current Tasks & Next Steps

We have completed **Phase 4: Document Management**. Key accomplishments include:

- **Implemented secure file upload system**: Configured Django's file handling with UUID-based filenames for security
- **Created role-based document access control**: Multi-level permissions (company, property, unit, private) with user/role restrictions
- **Built comprehensive document sharing system**: Users can share documents with notifications and audit trails
- **Developed document management UI**: Upload, view, download, delete functionality with category organization
- **Integrated document sections into all dashboards**: Role-appropriate document access for landlords, employees, and tenants
- **Added document categories**: Pre-populated with apartment management categories (leases, financial, maintenance, etc.)

We have completed **Phase 5: Maintenance System** with comprehensive enhancements. Key accomplishments include:

**Core Maintenance Features:**
- **Created comprehensive maintenance models**: Built MaintenanceRequest, MaintenanceCategory, MaintenancePhoto, MaintenanceUpdate, and MaintenanceInvoice models with full workflow support
- **Implemented secure photo upload system**: UUID-based file handling for maintenance request photos with multiple image support and download functionality
- **Built tenant request creation interface**: Complete form system allowing tenants to submit requests with photos, descriptions, and priority settings
- **Developed management interfaces for staff**: Landlord and employee dashboards with status updates, assignment capabilities, and progress tracking
- **Added complete status tracking system**: Full workflow from submission through completion with update timeline and audit trail

**Enhanced Invoice Management:**
- **Removed estimated cost tracking**: Streamlined system to focus on actual invoice-based cost tracking
- **Implemented full invoice CRUD operations**: Create, read, update, delete functionality for maintenance invoices
- **Added invoice-documents integration**: Invoices automatically create document records in "Maintenance Records" category
- **Built comprehensive invoice management**: Edit invoice details, replace files, proper version control

**Security & Access Control:**
- **Fixed document access control vulnerability**: Resolved security flaw where tenants could access invoices despite role restrictions
- **Implemented strict role-based invoice access**: Only landlords and employees can view financial information
- **Enhanced permission enforcement**: Proper isolation of sensitive financial data from tenants

**UI/UX Enhancements:**
- **Improved form field sizing**: Better padding and input field dimensions throughout maintenance interface
- **Enhanced photo management**: Download functionality for maintenance photos with hover controls
- **Optimized layout organization**: Moved invoices section for better visual hierarchy and wider display
- **Enhanced filter controls**: Larger, more usable filter dropdowns and search inputs on maintenance list
- **Added navbar dashboard navigation**: Clickable "AptMgmt" brand link for quick dashboard access

**System Integration:**
- **Seamless documents module integration**: Maintenance invoices appear in documents with proper categorization
- **Role-appropriate visibility**: Different user types see appropriate information based on their permissions
- **Comprehensive search and filtering**: Advanced list management with status, priority, and search capabilities
- **Scheduling functionality**: Date/time scheduling for maintenance appointments with assignment tracking

We have completed **Phase 6: Communication Features**. Key accomplishments include:

**Direct Messaging System:**
- **Built robust messaging models**: Created `MessageThread`, `Message`, `MessageAttachment`, and `MessageReadStatus` models to support threaded conversations.
- **Implemented role-based recipient selection**: Developed a dynamic form that populates the recipient list based on the sender's role, ensuring users can only message appropriate contacts (e.g., tenants can message their property's landlord and employees).
- **Created full-featured messaging UI**: Built templates for listing message threads, viewing individual threads, and composing new messages.
- **Enabled file attachments**: Users can attach multiple files to messages, which are securely stored and linked to the relevant message.
- **Added message notifications**: Integrated with the existing notification system to alert users to new messages.

**Community Board:**
- **Developed community post models**: Created `CommunityPost` and `CommunityPostAttachment` models for property-specific announcements and events.
- **Implemented role-based posting and moderation**: Landlords, employees, and tenants can create posts. Landlords and employees have moderation rights (hiding/deleting posts) within their assigned properties.
- **Built community board UI**: Created a central view for all community posts with filtering by property, plus forms for creating and editing posts.
- **Added support for event posts**: Included special fields for event dates and locations, which are displayed prominently on event-type posts.
- **Enabled file and image attachments for posts**: Users can attach multiple files and images to enrich their community posts.

We have completed **Phase 7: Calendar System**. Key accomplishments include:

**Core Calendar Features:**
- **Created comprehensive calendar models**: Built `CalendarEvent` and `WorkSchedule` models with proper relationships to properties, users, and maintenance requests
- **Implemented multi-view calendar interface**: Month, week, and day views with responsive design and intuitive navigation
- **Added role-based event management**: Full CRUD operations with proper permissions (landlords/employees can create/edit, tenants have view access)
- **Built event creation and editing system**: User-friendly forms with validation, assignment capabilities, and notification integration
- **Integrated maintenance request linking**: Automatic calendar event creation when maintenance is scheduled via Django signals

**Visual Calendar Features:**
- **Multi-day event spanning**: Events properly span across multiple days in all calendar views with visual continuity
- **Color-coded event types**: Visual distinction by event type (maintenance, meetings, inspections, etc.)
- **Smart event labeling**: Context-aware display showing appropriate information based on event duration and type
- **Proper date handling**: Fixed timezone issues to ensure events appear on correct dates

**Work Schedule Management:**
- **Employee schedule system**: Recurring work schedules with day-of-week patterns and effective date ranges
- **Schedule CRUD operations**: Create, read, update, delete work schedules for employees
- **Property-specific scheduling**: Work schedules tied to specific properties with company-level access control

**Calendar Integration:**
- **Dashboard navigation**: Calendar links added to all role-specific dashboards for easy access
- **Maintenance integration**: Scheduled maintenance automatically creates calendar events with proper assignment
- **Advanced filtering**: Property, type, priority, and assignment-based filtering across all calendar views
- **Event notifications**: Automatic notifications sent to assigned users when events are created or updated

**Technical Enhancements:**
- **Fixed template filter issues**: Added missing `add_form_control` and `add_checkbox_class` template filters for proper form styling
- **Improved date logic**: Resolved date offset issues in multi-day events using string-based date comparison
- **Enhanced event detail display**: Multi-day events now properly show start and end dates/times instead of appearing as single-day events
- **Calendar navigation**: Proper month/week/day navigation with current date defaults

**Current Status:**
The calendar system is fully functional with comprehensive event management, visual spanning of multi-day events, maintenance integration, and role-based access control. Users can create, view, and manage events across month, week, and day views with proper multi-day event handling. All timezone issues have been resolved and the system properly handles all-day events.

**Phase 7 Completion Summary:**
- ✅ Calendar models and database schema implemented
- ✅ Multi-view calendar interface (month, week, day) completed
- ✅ Event CRUD operations with role-based permissions
- ✅ Visual event spanning and color coding
- ✅ Work schedule management system
- ✅ Maintenance integration with automatic event creation
- ✅ Advanced filtering and timezone handling
- ✅ Event notifications and dashboard integration
- ✅ All identified bugs and display issues resolved

**Areas for Future Enhancement:**
- Additional calendar features like recurring events
- Calendar export/import functionality  
- More advanced scheduling features
- Calendar widget improvements

## Notification System Enhancement (Post-Phase 7)

**Enhanced Notification System** has been completed with significant improvements to user experience and functionality:

**Core Notification Features:**
- **Dynamic Document Notifications**: Automatic notifications when documents are assigned, shared, or uploaded by tenants
- **Smart Dropdown Display**: Notification bell dropdown now shows only unread notifications (maximum 5 most recent)
- **Real-time UI Updates**: AJAX-based interactions that immediately remove notifications from dropdown when clicked
- **Context Processor Integration**: Global notification data available to all templates through custom context processor
- **Notification Count Management**: Dynamic badge updates with real-time count adjustments

**User Experience Improvements:**
- **Immediate Feedback**: Clicked notifications fade out and disappear from dropdown instantly
- **Visual Distinction**: Clear differentiation between read and unread notifications with color coding and indicators
- **Graceful Degradation**: System works with or without JavaScript enabled
- **Comprehensive History**: Full notification list view maintains complete history while dropdown shows only new items

**Technical Implementation:**
- **AJAX Integration**: Seamless notification marking without page reloads
- **Dual Response Handling**: Views handle both AJAX and regular HTTP requests appropriately
- **Template Enhancement**: Updated base template with improved notification UI and JavaScript interactions
- **URL Routing**: Complete notification management with mark-as-read and bulk operations

**Document Integration:**
- **Automatic Tenant Notifications**: When tenants upload documents, landlords and employees receive immediate notifications
- **Manual Assignment Notifications**: Users assigned to documents during upload receive targeted notifications
- **Document Sharing Alerts**: Enhanced sharing system with immediate notification delivery
- **Smart Targeting**: Notifications respect company boundaries and role-based permissions

**Notification Management:**
- **Full List View**: Comprehensive notification history with pagination and filtering
- **Mark All Read**: Bulk operation to clear all unread notifications
- **Individual Management**: Granular control over notification read status
- **Persistent History**: Read notifications remain available in full list while being hidden from dropdown

This enhancement significantly improves the user experience by providing immediate, relevant notifications while maintaining a clean and uncluttered interface. The system now properly distinguishes between "new" notifications that require attention and historical notifications for reference.

We have completed **Phase 8: Financial Features**. Key accomplishments include:

**Core Financial Models:**
- **Created comprehensive financial database schema**: Built `PaymentSchedule`, `RentPayment`, `ExpenseRecord`, and `PaymentReceipt` models with full relationship mapping to existing property and user systems
- **Implemented multi-status payment tracking**: Complete workflow supporting Pending, Paid, Overdue, Partial, and Failed payment statuses with automatic transitions
- **Added payment validation and calculations**: Built-in validators, automatic total calculations, balance tracking, and overdue detection with property methods
- **Integrated with existing systems**: Seamless connections to property management, user roles, and notification systems

**Tenant Payment Interface:**
- **Built comprehensive payment dashboard**: Tenants can view their payment schedule, history, and current balance with clear status indicators
- **Implemented payment submission system**: User-friendly forms for tenants to submit payment information with reference numbers and notes
- **Added payment status tracking**: Real-time updates showing payment progress from submission to processing
- **Created intuitive UI/UX**: Clean, responsive design following existing platform patterns with dark mode support

**Payment Scheduling System:**
- **Developed landlord/employee scheduling tools**: Complete CRUD operations for creating and managing tenant payment schedules
- **Added flexible frequency options**: Support for monthly, quarterly, and annual payment schedules with customizable start/end dates
- **Implemented role-based access control**: Proper company and property isolation ensuring users only manage their assigned tenants
- **Built schedule management interface**: List views, detailed views, and editing capabilities with validation and error handling

**Payment History & Tracking:**
- **Created advanced filtering system**: Filter by status, payment method, date ranges with search functionality across tenant names, units, and reference numbers
- **Implemented comprehensive list views**: Paginated displays with visual indicators for overdue payments and balance information
- **Added detailed payment views**: Complete payment information including schedule details, audit trails, and action buttons
- **Built payment processing interface**: Staff can process tenant submissions, update amounts, and track payment methods

**Notification Integration:**
- **Enhanced existing notification system**: Automatic notifications for payment submissions, processing confirmations, and status updates
- **Added role-based notification targeting**: Tenants receive processing confirmations, staff receive submission alerts
- **Integrated with dashboard systems**: Proper notification flow respecting company boundaries and role permissions
- **Built notification audit trail**: Complete tracking of payment-related communications

**Dashboard Integration:**
- **Updated tenant dashboard**: Added "Rent Payments" button with direct access to payment interface
- **Enhanced landlord dashboard**: Created financial dropdown menu with access to payment schedules and history
- **Improved navigation flow**: Seamless transitions between related financial features
- **Maintained design consistency**: All new features follow existing UI patterns and styling

**Security & Access Control:**
- **Implemented strict role-based permissions**: Tenants only see their own payments, staff see company-wide data
- **Added company-level data isolation**: Proper multi-tenancy support preventing cross-company data access
- **Built audit trail system**: Complete tracking of who processed payments and when
- **Enhanced form validation**: Server-side and client-side validation for all financial data

**Technical Implementation:**
- **Created admin interfaces**: Complete Django admin integration for all financial models with proper fieldsets and filters
- **Built comprehensive forms**: Role-specific forms with dynamic field population and validation
- **Implemented advanced queries**: Efficient database queries with proper indexing and optimization
- **Added template system**: Reusable templates following platform conventions with proper error handling

**Phase 8 Completion Summary:**
- ✅ Financial models and database schema implemented
- ✅ Tenant payment interface with history and submissions
- ✅ Payment scheduling system for landlords/employees
- ✅ Advanced filtering and search capabilities
- ✅ Payment processing workflow with status tracking
- ✅ Notification system integration
- ✅ Dashboard navigation and UI integration
- ✅ Role-based access control and security measures
- ✅ Admin interfaces and management tools

**Current Status:**
The financial system is fully functional with comprehensive payment management, scheduling, and tracking capabilities. The platform now supports complete rent collection workflows from schedule creation through payment processing, with proper multi-tenancy, role-based access control, and notification integration.

**Areas for Future Enhancement:**
- Online payment processing integration (Stripe, PayPal)
- Financial reporting and analytics dashboards
- Automated late fee calculations and dunning processes
- Lease agreement integration with payment schedules
- Expense reporting and budgeting tools

## Calendar System Enhancements (Post-Phase 8)

**Automatic Maintenance Calendar Integration** has been completed with significant improvements to the calendar system:

**Automatic Calendar Event Creation:**
- **Maintenance Request Scheduling**: When a maintenance request status is changed to "SCHEDULED" with a scheduled_date, a calendar event is automatically created
- **Smart Event Details**: Calendar events include comprehensive information (title with "Maintenance:" prefix, property/unit details, description, location)
- **Intelligent Duration**: Uses estimated_completion time or defaults to 2-hour duration for maintenance appointments
- **Priority Mapping**: Emergency maintenance requests create HIGH priority calendar events, others default to MEDIUM priority
- **Duplicate Prevention**: System checks for existing calendar events before creating new ones to prevent duplicates

**Enhanced Calendar Visibility & Security:**
- **Tenant Isolation**: Tenants can only see calendar events for their own maintenance requests, not other tenants' requests
- **Property-Level Employee Access**: Employees now have proper property-level restrictions - they only see events for properties they're assigned to
- **Landlord Full Access**: Landlords maintain company-wide visibility of all calendar events
- **Role-Based Event Filtering**: Updated visibility logic ensures proper data isolation across all user roles

**Calendar Event Assignment:**
- **Automatic Tenant Assignment**: Requesting tenants are automatically assigned to their maintenance calendar events
- **Worker Assignment**: If a maintenance worker is assigned to the request, they're also assigned to the calendar event
- **Visibility Through Assignment**: Tenants can see maintenance events through direct assignment in addition to ownership-based visibility

**User Model Enhancements:**
- **Apartment Unit Field**: Added `apartment_unit` field to User model to properly associate tenants with their specific units
- **Invitation System Update**: Fixed invitation acceptance process to properly transfer apartment_unit from invitation to user profile
- **Admin Interface Update**: Enhanced Django admin to include apartment_unit field for easy tenant management

**Maintenance Request Form Improvements:**
- **Read-Only Unit Display**: Tenant maintenance request form now shows apartment unit as read-only field, maintaining visual balance
- **Automatic Unit Assignment**: Tenant's apartment unit is automatically set during maintenance request creation
- **Error Handling**: Clear messaging for tenants without assigned apartment units

**Calendar Navigation Fixes:**
- **Month View Navigation**: Fixed navigation arrows to properly change months using URL parameters
- **Date Initialization**: Resolved timezone issues causing calendar to display wrong month on page load
- **JavaScript Date Handling**: Improved date parsing to avoid timezone conversion problems in month view
- **Multi-Day Event Display**: Fixed maintenance events incorrectly appearing as multi-day when they're same-day events

**Technical Implementation:**
- **Django Model Updates**: Added apartment_unit foreign key to User model with proper migration
- **View Logic Enhancement**: Updated calendar visibility filters with role-specific access control
- **Template Improvements**: Fixed JavaScript date initialization and navigation in month view
- **Form Logic Updates**: Modified maintenance request forms to handle apartment unit automatically for tenants

**Security & Access Control:**
- **Strict Tenant Isolation**: Tenants cannot see other tenants' maintenance appointments in calendar
- **Property-Level Employee Restrictions**: Employees from Property A cannot see maintenance from Property B
- **Maintenance Event Filtering**: Separate visibility rules for maintenance vs non-maintenance calendar events
- **Proper Data Boundaries**: All calendar access respects company and property boundaries

This enhancement provides seamless integration between the maintenance system and calendar, ensuring all stakeholders are automatically informed when maintenance is scheduled while maintaining strict security boundaries between different user groups.

We are currently working on **Phase 9: Detailed Views** with comprehensive metric card expansions. Key accomplishments so far include:

**Dashboard Metric Card Enhancements:**
- **Replaced hardcoded data with real calculations**: All dashboard metric cards now display actual data from the database instead of placeholder values
- **Enhanced Monthly Rent Income**: Changed calculation from payment tracking to occupied unit rent totals, providing accurate potential monthly income
- **Fixed Monthly Expenses**: Added maintenance invoice integration to include both ExpenseRecord and MaintenanceInvoice costs in expense calculations
- **Updated Payment Status**: Implemented real-time payment performance tracking with color-coded indicators and late tenant counts
- **Corrected Maintenance Requests**: Excluded completed requests from active count to show actual workload requiring attention

**Expanded Detailed Views:**
- **Monthly Rent Income Detail View** (`/dashboard/rent-income/`): Comprehensive breakdown of rent payments with status tracking, property filtering, and detailed payment tables
- **Monthly Expenses Detail View** (`/dashboard/monthly-expenses/`): Complete expense analysis showing both maintenance costs and general expenses with category breakdowns
- **Maintenance Requests Detail View** (`/dashboard/maintenance-requests/`): Advanced request management with status filtering, priority indicators, and comprehensive search capabilities
- **Payment Status Detail View** (`/dashboard/payment-status/`): Detailed payment performance tracking with collection rates, outstanding amounts, and tenant-specific analysis

**Advanced Filtering & Search Systems:**
- **Property-based filtering**: All detailed views support company-wide or property-specific data analysis
- **Status and priority filtering**: Comprehensive filtering options for maintenance requests and payment statuses
- **Search functionality**: Full-text search across tenant names, unit numbers, descriptions, and reference numbers
- **Clear filter options**: Easy reset functionality to remove all applied filters

**Visual Enhancements & User Experience:**
- **Color-coded performance indicators**: Dynamic visual feedback based on performance thresholds (green ≥90%, yellow 70-89%, red <70%)
- **Clickable metric cards**: All dashboard cards now navigate to their respective detailed views while preserving property context
- **Comprehensive summary cards**: Each detailed view includes multiple summary metrics for quick assessment
- **Status badges and indicators**: Clear visual status representation throughout all detailed views

**Financial Analytics & Reporting:**
- **Collection rate tracking**: Percentage-based payment performance monitoring
- **Outstanding balance analysis**: Real-time tracking of pending and overdue amounts
- **Expense categorization**: Detailed breakdown between maintenance costs and general operating expenses
- **Tenant payment behavior**: Individual tenant payment status and history tracking

**Multi-Tenancy & Security:**
- **Company-level data isolation**: All views respect company boundaries and user access levels
- **Property-specific access control**: Employees assigned to specific properties see filtered data appropriately
- **Role-based permissions**: Landlords and employees only have access to detailed financial and operational views
- **Context preservation**: Property selections are maintained when navigating between dashboard and detailed views

**Technical Implementation:**
- **Efficient database queries**: Optimized queries with proper select_related and prefetch_related for performance
- **Real-time calculations**: Dynamic metric calculations based on current database state
- **Template consistency**: All detailed views follow established UI patterns and responsive design principles
- **Navigation integration**: Seamless flow between dashboard overview and detailed analysis

**Phase 9 Completion Summary:**
- ✅ Monthly Rent Income expanded view with real payment data
- ✅ Monthly Expenses detailed analysis with maintenance invoice integration
- ✅ Maintenance Requests comprehensive management interface
- ✅ Payment Status detailed performance tracking
- ✅ Advanced filtering and search capabilities across all views
- ✅ Property-specific and company-wide data analysis
- ✅ Color-coded performance indicators and visual feedback
- ✅ Clickable navigation from dashboard metric cards
- ✅ Multi-tenancy support with proper access control
- ✅ Real-time data calculations replacing hardcoded values

**Current Status:**
The dashboard system now provides comprehensive drill-down capabilities from high-level metric summaries to detailed operational analysis. Landlords and property managers can quickly assess overall performance through the dashboard cards and dive deep into specific areas requiring attention through the expanded detailed views. All financial calculations are based on real data, providing accurate insights for decision-making.

**Areas for Future Enhancement:**
- Additional metric card expansions (Occupancy Rate, Lease Expirations, Vacant Units)
- Historical trend analysis and comparative reporting
- Export functionality for detailed reports
- Advanced analytics and forecasting capabilities
- Bulk action capabilities from detailed views 