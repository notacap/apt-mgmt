# Project Context

## Project Overview

This project is a comprehensive web-based platform for apartment management companies, designed to streamline operations between landlords/owners, employees, and tenants. The technical stack includes Django for the backend, with HTMX, Alpine.js, and Tailwind CSS for the frontend. The platform features role-based dashboards, document management, maintenance tracking, rent collection, and communication tools.

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

## Key Architectural Decisions & Fixes
- **Corrected User/Property Hierarchy**: The invitation system was updated to enforce the correct business logic. When a landlord or employee sends an invitation, they must now select a specific property belonging to their company. The invited user is automatically associated with both the company and the selected property upon registration.
- **Programmatic Group Permissions**: User groups ("Landlords", "Employees", "Tenants") and their associated model permissions are now created automatically via a Django data migration. This ensures a consistent and version-controlled permission setup.
- **Fixed Admin User Creation**: The Django admin for the User model was customized to display and allow editing of the custom `role` and `company` fields. This fixed a critical bug where users created via the admin were not being assigned a role, causing login redirection to fail.
- **Resolved Migration Conflicts**: A significant migration conflict (InconsistentMigrationHistory) arose after implementing the custom user model. This was resolved by resetting the `users` app migrations and rebuilding them, which required a one-time database reset and recreation of user accounts.

## Current Tasks & Next Steps

We have completed **Phase 3: Core Dashboard Features**.

### Phase 3 Accomplishments:
- **Built notification system with badge display**: Created a `Notification` model in the `communication` app with notification types, recipient targeting, and badge display in the header navigation.
- **Created reusable metric card components**: Developed reusable metric card template with customizable icons, colors, and trend indicators.
- **Implemented landlord dashboard with all metric cards**: Built comprehensive landlord dashboard featuring all required metrics (rent income, expenses, revenue, maintenance requests, payment status, occupancy rate, lease expirations, vacant units) with property selector and recent activity sections.
- **Added property selector with filtered views**: Implemented property filtering dropdown in the landlord dashboard header.
- **Created employee dashboard layout**: Built employee-focused dashboard with maintenance management, schedule view, document access, and communication features.
- **Built tenant dashboard structure**: Developed tenant self-service portal with rent management, maintenance requests, document access, and messaging capabilities.

We are now ready to begin **Phase 4: Document Management**.

The immediate next task is:
- **Set up file upload system with secure storage**: This will involve configuring Django's file handling, creating secure upload endpoints, and implementing proper access controls for documents. 