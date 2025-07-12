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

We are now beginning **Phase 3: Core Dashboard Features**.

The immediate next task is:
- **Build notification system with badge display**: This will involve creating a `Notification` model in the `communication` app and the necessary logic to display notifications with a badge in the UI. 