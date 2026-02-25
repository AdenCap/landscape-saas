# New CRM Features Guide

This document outlines the 10 major CRM features added to complete the home service business management system.

## Features Overview

### 1. Customer Portal (`/portal/`)
- **Purpose**: Allow customers to log in and view their invoices, estimates, and service history
- **Access**: Customers receive an access token when their account is created
- **Features**:
  - View all invoices and payment history
  - View estimates and accept them
  - View service history
  - Dashboard with account summary
- **Setup**: Portal access is automatically created when a customer is added (via signal)

### 2. SMS Integration (Twilio)
- **Purpose**: Send SMS reminders and notifications
- **Configuration**: Add to `.env`:
  ```
  TWILIO_ACCOUNT_SID=your_account_sid
  TWILIO_AUTH_TOKEN=your_auth_token
  TWILIO_PHONE_NUMBER=+1234567890
  ```
- **Usage**: Use `customers.sms_utils.send_sms()` function
- **Automation**: Used in management commands for reminders

### 3. Lead Management (`/leads/`)
- **Purpose**: Track prospects from inquiry to conversion
- **Features**:
  - Lead pipeline (new → contacted → qualified → converted)
  - Lead source tracking
  - Follow-up reminders
  - Convert leads directly to customers
- **Access**: Owner role only

### 4. Customer Reviews (`/reviews/`)
- **Purpose**: Collect and display customer reviews/ratings
- **Features**:
  - 1-5 star ratings
  - Review comments
  - Link reviews to jobs
  - Public/private review display
- **Automation**: Review requests sent via management command

### 5. Equipment & Vehicle Tracking (`/equipment/`)
- **Purpose**: Track equipment, vehicles, and maintenance
- **Features**:
  - Equipment inventory
  - Maintenance scheduling
  - Usage tracking (hours, miles, fuel)
  - Maintenance cost tracking
- **Automation**: Maintenance due alerts via management command

### 6. Customer Self-Service (`/requests/public/`)
- **Purpose**: Allow customers to request services/estimates online
- **Features**:
  - Public request form (no login required)
  - Request management workflow
  - Link requests to estimates
- **Access**: Public form, owner manages requests

### 7. Satisfaction Surveys (`/surveys/`)
- **Purpose**: Automated customer satisfaction surveys
- **Features**:
  - Multi-dimensional ratings (overall, quality, timeliness, communication)
  - NPS (Net Promoter Score) tracking
  - Open-ended feedback
- **Automation**: Survey invitations sent after job completion

### 8. Referral Tracking (`/referrals/`)
- **Purpose**: Track referral sources and rewards
- **Features**:
  - Unique referral codes
  - Referral status tracking
  - Reward amount tracking
  - Conversion tracking
- **Access**: Owner role only

### 9. Inventory Management (`/inventory/`)
- **Purpose**: Track materials and stock levels
- **Features**:
  - Inventory item tracking
  - Stock level monitoring
  - Low stock alerts
  - Purchase order management
  - Inventory transactions
- **Automation**: Low stock alerts via management command

### 10. Document Storage (`/documents/`)
- **Purpose**: Centralized document management
- **Features**:
  - Upload documents (contracts, photos, permits, etc.)
  - Link to customers, jobs, invoices, estimates
  - Customer-visible documents (accessible in portal)
  - Document categorization

## Management Commands (Automation)

All commands can be run manually or scheduled via cron/task scheduler:

### Daily Commands
```bash
# Send job reminders for tomorrow
python manage.py send_job_reminders

# Send payment reminders for overdue invoices
python manage.py send_payment_reminders

# Check for low stock items
python manage.py check_low_stock

# Check for equipment maintenance due
python manage.py check_maintenance_due
```

### Periodic Commands (1-3 days after events)
```bash
# Send review requests (1-3 days after job completion)
python manage.py send_review_requests

# Send survey invitations (1-2 days after job completion)
python manage.py send_survey_invitations

# Send lead follow-ups (on scheduled follow-up date)
python manage.py send_lead_followups
```

### Recommended Cron Schedule
```cron
# Daily at 8 AM
0 8 * * * cd /path/to/project && python manage.py send_job_reminders
0 8 * * * cd /path/to/project && python manage.py send_payment_reminders
0 8 * * * cd /path/to/project && python manage.py check_low_stock
0 8 * * * cd /path/to/project && python manage.py check_maintenance_due

# Daily at 9 AM (for follow-ups)
0 9 * * * cd /path/to/project && python manage.py send_lead_followups

# Daily at 10 AM (for post-service communications)
0 10 * * * cd /path/to/project && python manage.py send_review_requests
0 10 * * * cd /path/to/project && python manage.py send_survey_invitations
```

## Setup Instructions

### 1. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Configure Twilio (Optional)
Add to your `.env` file:
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

### 3. Set Up Scheduled Tasks
Configure your task scheduler (cron, Celery, etc.) to run the management commands.

### 4. Customer Portal Access
- Portal access is automatically created when customers are added
- Access tokens are generated automatically
- Send customers their access token via email/SMS to log in

## URL Routes

All new features are accessible via:
- `/portal/` - Customer portal
- `/leads/` - Lead management
- `/reviews/` - Customer reviews
- `/equipment/` - Equipment tracking
- `/requests/` - Service requests
- `/surveys/` - Satisfaction surveys
- `/referrals/` - Referral tracking
- `/inventory/` - Inventory management
- `/documents/` - Document storage

## Integration Points

All features integrate with existing systems:
- **Customers**: All features link to customer records
- **Jobs**: Reviews, surveys, equipment usage link to jobs
- **Billing**: Documents, requests link to invoices/estimates
- **Businesses**: All features are scoped to businesses

## Notes

- All features respect customer communication preferences (email/SMS/both)
- Management commands handle errors gracefully
- Templates use the existing base.html design system
- All features are accessible via admin interface
- Customer portal uses token-based authentication (simple and secure)
