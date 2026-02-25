# Employee/Crew Features Guide

This document outlines all the features available to employees/crew members in the system.

## Crew Dashboard & Navigation

### Today's Jobs (`/jobs/crew/`)
- View all jobs assigned to you for today
- Clock in/out widget at the top
- Quick actions: View details, Report issue, Upload photo, Call customer, Navigate
- Gate codes displayed prominently
- Job status badges (scheduled, in progress, completed)
- Photo requirements clearly indicated

### All My Jobs (`/jobs/crew/my-jobs/`)
- View all your assigned jobs (past, present, future)
- Filter by status (scheduled, in progress, completed, skipped)
- Filter by date (today, upcoming, past)
- Quick access to job details

### Job Detail View (`/jobs/crew/<job_id>/`)
- Complete job information
- Customer and property details
- Gate codes and property notes
- Job notes (view and add)
- Service items list
- Completion photos gallery
- Reported issues
- Quick actions:
  - Navigate to job (Apple Maps/Google Maps)
  - Call customer
  - Report issue
  - Upload photo
  - Add note
- Job actions: Start job, Complete job

## Time Tracking

### Clock In/Out (`/time/clock/`)
- Simple clock in/out interface
- GPS location capture (optional, requires permission)
- Today's hours summary
- List of today's time entries
- Visual status indicators

### Features:
- **GPS Tracking**: Optional location capture when clocking in/out
- **Today's Summary**: See total hours worked today
- **Entry History**: View all clock in/out entries for the day
- **Status Display**: Clear indication of current clock status

## Job Management

### Start Job
- Mark job as "in progress"
- Available from today's jobs or job detail view
- One-click action

### Complete Job
- Mark job as "completed"
- Requires completion photo if business has that requirement enabled
- Automatically triggers billing workflow (owner handles)

### Add Job Notes
- Add timestamped notes to jobs
- Notes include your name and timestamp
- View all notes in job detail view
- Useful for reporting issues, documenting work, etc.

### Upload Completion Photos
- Upload proof-of-work photos
- Required before completion if business requires it
- View all photos in gallery
- Photos stored with timestamp and your name

### Report Issues
- Report job issues (equipment, access, damage, customer requests, etc.)
- Upload photos with issue reports
- Owner automatically notified
- Issues tracked and can be resolved by owner

## Communication

### View Job Information
- Customer name and contact info
- Property address
- Gate codes
- Property notes
- Service requirements
- Job notes (from owner or other crew)

### Quick Actions
- **Call Customer**: Direct phone link from job
- **Navigate**: Open in Apple Maps/Google Maps with address or coordinates
- **View Details**: Full job information

## Mobile Optimization

All crew interfaces are optimized for mobile use:
- Large, touch-friendly buttons
- Responsive layouts
- Quick actions prominently displayed
- Minimal scrolling required
- GPS integration for location services

## Permissions & Access

Crew members can:
- ✅ View jobs assigned to them or their crew
- ✅ Clock in/out
- ✅ Start and complete jobs
- ✅ Add notes to jobs
- ✅ Upload completion photos
- ✅ Report issues
- ✅ View job details
- ✅ View their time entries
- ✅ Request time off

Crew members cannot:
- ❌ Create or delete jobs
- ❌ Edit customer information
- ❌ View financial data (invoices, payments)
- ❌ Approve time entries
- ❌ Access admin functions

## Best Practices

1. **Clock In/Out**: Always clock in when starting work and clock out when done
2. **Job Notes**: Add notes for any important information (gate code changed, customer requests, etc.)
3. **Completion Photos**: Take photos as proof of work, especially for completed services
4. **Issue Reporting**: Report issues immediately so owner can address them
5. **Navigation**: Use the navigate button to get directions to job locations
6. **Communication**: Use the call button to contact customers if needed

## Troubleshooting

**Can't see a job?**
- Check if it's assigned to you or your crew
- Check the date filter
- Contact owner if you believe you should have access

**Can't complete job?**
- Check if completion photo is required
- Upload at least one photo if required
- Contact owner if issue persists

**Clock in/out not working?**
- Check your internet connection
- Try refreshing the page
- Contact owner if problem continues
