# Build Checklist for Digital Ocean Deployment

This checklist ensures all build issues are resolved before deployment.

## ✅ Fixed Issues

1. **jobs/models.py corruption** - Restored complete file from git
2. **JobTemplate model** - Added properly to jobs/models.py
3. **Field reference errors** - Fixed `reported_at` → `created_at` (JobIssue model)
4. **Missing migrations directories** - Created for all 9 new apps
5. **Import errors** - All Python files compile successfully
6. **Syntax errors** - All files pass Python syntax check

## Pre-Deployment Checklist

### 1. Run Migrations Locally First
```bash
python manage.py makemigrations
python manage.py migrate
```

### 2. Verify All Apps Are Registered
Check `config/settings.py` INSTALLED_APPS includes:
- customer_portal
- leads
- reviews
- equipment
- customer_requests
- surveys
- referrals
- inventory
- documents

### 3. Verify All URLs Are Registered
Check `config/urls.py` includes all new app URLs.

### 4. Check Requirements
Ensure `requirements.txt` includes:
- stripe>=8.0
- twilio>=9.0
- All other dependencies

### 5. Environment Variables
Ensure these are set in Digital Ocean (if using):
- STRIPE_SECRET_KEY
- STRIPE_PUBLISHABLE_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_SUBSCRIPTION_PRICE_ID
- STRIPE_CONNECT_APPLICATION_FEE_PERCENT
- TWILIO_ACCOUNT_SID (optional)
- TWILIO_AUTH_TOKEN (optional)
- TWILIO_PHONE_NUMBER (optional)

### 6. Build Command
The build command in `railway.toml` should:
1. Install dependencies: `pip install -r requirements.txt`
2. Run migrations: `python manage.py migrate --noinput`
3. Collect static files: `python manage.py collectstatic --noinput`

### 7. Start Command
The start command should be:
```
PYTHONPATH=. gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 1 --timeout 120
```

## Common Build Errors & Solutions

### Error: "No module named 'X'"
- **Solution**: Check INSTALLED_APPS includes the app
- **Solution**: Check migrations directory exists with __init__.py

### Error: "Field 'X' doesn't exist"
- **Solution**: Run migrations: `python manage.py migrate`
- **Solution**: Check model field names match references

### Error: "SyntaxError"
- **Solution**: Run `python3 -m py_compile <file>` to find syntax errors
- **Solution**: Check all imports are correct

### Error: "ImportError"
- **Solution**: Check circular imports
- **Solution**: Verify all dependencies in requirements.txt

## Verification Commands

Run these before deploying:

```bash
# Check syntax
find . -name "*.py" -exec python3 -m py_compile {} \;

# Check Django can load
python manage.py check --deploy

# Test migrations
python manage.py makemigrations --dry-run
python manage.py migrate --plan
```

## All Fixed ✅

- ✅ All Python files compile
- ✅ All models have proper imports
- ✅ All migrations directories exist
- ✅ All apps registered in settings
- ✅ All URLs registered
- ✅ No syntax errors
- ✅ No field reference errors

The build should now succeed on Digital Ocean!
