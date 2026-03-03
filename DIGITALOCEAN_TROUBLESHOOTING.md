# DigitalOcean Deployment Troubleshooting Guide

If your deployment is failing on DigitalOcean App Platform, follow these steps in order:

## Step 1: Check Build Logs

1. Go to DigitalOcean Dashboard → Your App → **Deployments**
2. Click on the **failed deployment**
3. Open the **Build Logs** tab
4. Scroll to the **bottom** (last 20-30 lines show the actual error)
5. Copy the error message

## Step 2: Common Issues and Fixes

### Issue 1: "Database URL not set" or "PG_URL must be set"

**Error message:**
```
[DATABASE] FATAL: PG_URL or POSTGRES_URL must be set when running on this platform
RuntimeError: Database URL not set
```

**Fix:**
1. Go to DigitalOcean Dashboard → Your App → **Settings**
2. Click on your **web service** component (not "Static Site" or "Worker")
3. Go to **Environment Variables**
4. Click **Add Variable** or **Edit**
5. Add:
   - **Key:** `PG_URL`
   - **Value:** Your full Supabase connection URI (see "Get PG_URL" below)
   - **Scope:** **Run Time** (CRITICAL - must be Run Time, not Build)
6. Click **Save**
7. **Redeploy** the app

### Issue 2: "No route to host" or Database Connection Failed

**Error message:**
```
OperationalError: could not connect to server
No route to host
```

**Fix:**
1. **Check if Supabase is paused:**
   - Go to [Supabase Dashboard](https://supabase.com/dashboard)
   - If you see "Project is paused" or "Restore project", click **Restore**
   - Wait until the project is active (green status)
   - Redeploy your app

2. **Try Connection Pooler (Session mode):**
   - In Supabase: **Project Settings** → **Database** → **Connection string**
   - Choose **URI**, then select **Session mode** (port 6543)
   - Copy the URI (it will have `pooler.supabase.com` in the hostname)
   - Replace `[YOUR-PASSWORD]` with your actual password
   - Update `PG_URL` in DigitalOcean with this new URI
   - Redeploy

3. **Verify PG_URL format:**
   - Should be: `postgresql://postgres.xxxxx:PASSWORD@db.xxxxx.supabase.co:5432/postgres`
   - No quotes, no spaces
   - Password must be URL-encoded if it contains special characters (`@`, `#`, `%`, `/`, `?`)

### Issue 3: Build Command Failing

**Error message:**
```
ModuleNotFoundError: No module named '...'
ERROR: Could not find a version that satisfies the requirement
```

**Fix:**
1. Verify your **Build Command** is exactly:
   ```bash
   pip install --no-cache-dir -r requirements.txt && python manage.py collectstatic --noinput
   ```

2. Check Python version:
   - DigitalOcean defaults to Python 3.13
   - If packages fail, try setting Python version to 3.11 or 3.12 in the dashboard
   - Settings → Your web service → **Environment** → Python version

3. If `collectstatic` fails:
   - Check the error message in build logs
   - Common issues: missing `STATIC_ROOT` in settings, file permissions
   - The app.yaml should handle this correctly

### Issue 4: Migrations Failing

**Error message:**
```
django.db.utils.OperationalError: ...
Migration errors
```

**Fix:**
1. **Check PG_URL is set correctly** (see Issue 1)
2. **Verify database is accessible:**
   - Supabase project is not paused
   - Connection URI is correct
   - Password is correct and URL-encoded if needed

3. **Check migration command:**
   - Run command should include: `python manage.py migrate --noinput`
   - This runs AFTER the build, at runtime

### Issue 5: App Won't Start / Port Issues

**Error message:**
```
Address already in use
Port 8080 already in use
```

**Fix:**
1. Verify **HTTP Port** is set to `8080` in the web service settings
2. Verify **Run Command** uses `$PORT`:
   ```bash
   python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120
   ```
3. DigitalOcean sets `$PORT` automatically - don't hardcode it

## Step 3: Get Your PG_URL (Supabase)

1. Go to [Supabase Dashboard](https://supabase.com/dashboard) → Your project
2. Click **Project Settings** (gear icon) → **Database**
3. Under **Connection string**, choose **URI**
4. Copy the URI - it looks like:
   ```
   postgresql://postgres.[PROJECT_REF]:[YOUR-PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
5. **Replace `[YOUR-PASSWORD]`** with your actual database password
6. If password has special characters, URL-encode them:
   - `@` → `%40`
   - `#` → `%23`
   - `%` → `%25`
   - `/` → `%2F`
   - `?` → `%3F`
7. Paste the full string as `PG_URL` value in DigitalOcean (no quotes)

## Step 4: Verify Configuration

### Required Environment Variables (on web service, Run Time scope):

| Variable | Required | Notes |
|----------|----------|-------|
| `PG_URL` | **YES** | Full Supabase connection URI |
| `DJANGO_SECRET_KEY` | **YES** | Long random string (50+ chars) |

### Build & Run Commands:

**Build Command:**
```bash
pip install --no-cache-dir -r requirements.txt && python manage.py collectstatic --noinput
```

**Run Command:**
```bash
python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

**HTTP Port:** `8080`

## Step 5: Verify Deployment

After fixing issues and redeploying:

1. **Check Runtime Logs:**
   - DigitalOcean Dashboard → Your App → **Runtime Logs**
   - Look for: `[DATABASE] Using PostgreSQL at db.xxxx.supabase.co`
   - If you see `[DATABASE] Using SQLite`, `PG_URL` is not set correctly

2. **Test Database Connection:**
   - Set `DB_CHECK_SECRET` environment variable (any string, e.g. `mysecret123`)
   - After deploy, visit: `https://your-app.ondigitalocean.app/api/db-check/?key=mysecret123`
   - Should show: "Database: PostgreSQL" and "Connection: OK"

3. **Test App:**
   - Visit your app URL
   - Try logging in or accessing the homepage
   - Check for any errors in Runtime Logs

## Quick Checklist

- [ ] `PG_URL` is set on **web service** component (not app-level)
- [ ] `PG_URL` scope is **Run Time** (not Build)
- [ ] Supabase project is **active** (not paused)
- [ ] Build Command is correct (no migrate in build)
- [ ] Run Command includes migrate and gunicorn
- [ ] HTTP Port is set to 8080
- [ ] `DJANGO_SECRET_KEY` is set
- [ ] Redeployed after making changes

## Still Not Working?

1. **Copy the exact error** from Build Logs or Runtime Logs
2. **Check the last 30 lines** of the logs (most relevant errors are at the end)
3. **Verify all environment variables** are set correctly
4. **Check Supabase status** - ensure project is active
5. **Try a fresh deploy** - sometimes cached builds cause issues

## Common Mistakes

❌ Setting `PG_URL` at app-level instead of web service component  
❌ Setting `PG_URL` scope to "Build" instead of "Run Time"  
❌ Forgetting to replace `[YOUR-PASSWORD]` in the Supabase URI  
❌ Not URL-encoding special characters in password  
❌ Supabase project is paused  
❌ Running `migrate` in build command (should be in run command)  
❌ Hardcoding port instead of using `$PORT`
