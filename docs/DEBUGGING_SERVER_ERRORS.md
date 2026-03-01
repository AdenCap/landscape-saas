# Debugging Server Errors on DigitalOcean

## Quick Diagnostic

### Step 1: Check Health Endpoint

Visit this URL in your browser (replace with your domain):
```
https://your-app.ondigitalocean.app/health/
```

This will show:
- Database connection status
- Database engine being used
- Any errors
- Configuration issues

### Step 2: Check Runtime Logs

1. Go to DigitalOcean Dashboard
2. Your App → **Runtime Logs** tab
3. Look for:
   - Database connection errors
   - Migration errors
   - Any "ERROR" or "CRITICAL" messages

### Step 3: Check Build Logs

1. Your App → **Deployments** tab
2. Click on the latest deployment
3. Check **Build Logs** for:
   - Migration errors
   - Import errors
   - Configuration errors

## Common Server Errors

### 500 Internal Server Error

**Check:**
1. Runtime Logs for the exact error
2. Health endpoint: `/health/`
3. Database connection status

**Common causes:**
- Database connection failed
- Missing environment variable
- Migration error
- Import error

### Database Connection Error

**Symptoms:**
- Logs show "could not connect to server"
- Health endpoint shows "connection": "failed"

**Fix:**
1. Verify `DATABASE_URL` is set correctly
2. Check Trusted Sources in database settings
3. Verify SSL is included (`?sslmode=require`)
4. Test connection string format

### Migration Error

**Symptoms:**
- Build logs show migration errors
- "relation does not exist" errors

**Fix:**
1. Make sure build command includes: `python manage.py migrate --noinput`
2. Check migration files are valid
3. Try running migrations manually if possible

### Import Error

**Symptoms:**
- "ModuleNotFoundError" in logs
- "ImportError" in logs

**Fix:**
1. Check `requirements.txt` includes all packages
2. Verify build installs dependencies
3. Check for missing Python packages

## Getting the Exact Error

### Method 1: Health Endpoint

Visit: `https://your-app.ondigitalocean.app/health/`

This shows JSON with:
- Database status
- Connection errors
- Configuration issues

### Method 2: Runtime Logs

1. DigitalOcean Dashboard → Your App
2. **Runtime Logs** tab
3. Look for red error messages
4. Copy the full error message

### Method 3: Enable DEBUG (temporarily)

**Warning: Only for debugging, disable after!**

1. Add environment variable:
   - Key: `DJANGO_DEBUG`
   - Value: `1`
2. Redeploy
3. Error pages will show full traceback
4. **Disable after debugging!**

## What to Share for Help

If you need help, share:

1. **Exact error message** from Runtime Logs
2. **Health endpoint response** (visit `/health/`)
3. **Build logs** (from latest deployment)
4. **DATABASE_URL format** (without password):
   - `postgresql://user:***@host:port/db?sslmode=require`

## Quick Fixes to Try

### Fix 1: Verify DATABASE_URL

1. Check it's set in App-Level Environment Variables
2. Verify format: `postgresql://user:pass@host:port/db?sslmode=require`
3. Make sure it includes `?sslmode=require`
4. Redeploy

### Fix 2: Check Trusted Sources

1. Database → Trusted Sources
2. Add your app's IP or `0.0.0.0/0`
3. Save

### Fix 3: Verify Build Command

App → Settings → General → Build Command should be:
```
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

### Fix 4: Check Migrations

If migrations are failing:
1. Check build logs for migration errors
2. Verify all migration files are valid
3. Try resetting database (if no important data)

## Still Stuck?

1. Visit `/health/` endpoint and share the response
2. Copy the exact error from Runtime Logs
3. Check if it's a database, migration, or import error
4. Share the error message and I can help fix it!
