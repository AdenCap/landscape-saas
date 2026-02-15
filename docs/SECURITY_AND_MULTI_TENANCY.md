# Security & Multi-Tenancy

## Multi-tenant design

- **One platform, many businesses.** Each company (tenant) has its own:
  - **Business** record (name, logo, email/SMTP, settings).
  - **Users** (owners and crew) linked to that business.
  - **Data** (clients, properties, jobs, invoices, estimates, etc.) scoped to that business.

- **Strict data isolation.** Every view that shows or changes data uses `get_business(request)` and filters by that business. Normal users never see or edit another business’s data.

- **Separate logins.** Each business has its own owner and crew accounts. There is no shared login across companies; only the platform administrator (you) has a separate superuser account.

## Platform administrator (you)

- **Who:** The Django user with **Superuser** checked (e.g. the first account you create with `manage.py createsuperuser`).

- **What you can do:**
  - Log in at `/admin/` to manage all businesses, users, and data.
  - Go to **Platform admin** at `/platform/` to see a list of all businesses.
  - Click **Enter dashboard** for any business to open that company’s dashboard and use the app as if you were that business (for support and troubleshooting).
  - Use the **Exit** control (banner or sidebar) to leave that business and return to platform admin.

- **Important:** Only superusers can access `/platform/` and “view as” a business. Regular owners and crew cannot.

## Security practices

1. **Production**
   - Set `DJANGO_DEBUG=0` (or `False`) so error details are not shown to users.
   - Use **HTTPS** so login and data are encrypted in transit.
   - Set a strong `SECRET_KEY` (e.g. from env) and keep it secret.
   - Restrict `ALLOWED_HOSTS` to your real domain(s).

2. **Passwords**
   - Rely on Django’s default password validation (length, non-numeric, etc.).
   - Optional 2FA: pip install django-otp qrcode, add apps and OTPMiddleware; owners enable in Settings.

3. **Sensitive data**
   - Gmail/SMTP and QuickBooks credentials are stored per business in the database. Restrict DB and backup access.
   - Do not commit `.env` or any file containing secrets.

4. **Audit**
   - When you use “Enter dashboard” as a business, the blue banner shows you are viewing as that company. Use this only for support; avoid making changes unless needed.

## Summary

- **Companies:** Many businesses, each with its own users and data.
- **You:** One platform admin (superuser) who can open any business’s dashboard from `/platform/` for support.
- **Security:** Data scoped by business, HTTPS and no debug in production, strong secrets and restricted access.
