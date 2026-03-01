# DigitalOcean Database Not Working - Step-by-Step Fix

## Immediate Steps to Fix

### Step 1: Check What's Actually Set

1. **DigitalOcean Dashboard** → Your App
2. **Settings** → **App-Level Environment Variables**
3. **Look for `DATABASE_URL`** - is it there?
4. **If it's there:** Copy the first 50 characters (without the password) so we can see the format
5. **If it's NOT there:** That's the problem - DigitalOcean didn't set it automatically

### Step 2: If DATABASE_URL is Missing

**This is the most common issue!**

1. **Go to Databases** → Your database
2. **Connection Details** tab
3. **Copy the URI connection string** (the full one)
4. **Go to App** → **Settings** → **Environment Variables**
5. **Add Variable:**
   - **Key:** `DATABASE_URL`
   - **Value:** Paste the FULL connection string
   - **Scope:** Run Time
6. **Save**

**Important:** The connection string should look like:
```
postgresql://doadmin:password@db-host:25060/defaultdb?sslmode=require
```

### Step 3: Verify Trusted Sources

**This is critical - even if DATABASE_URL is set, this can block connections:**

1. **Databases** → Your database
2. **Trusted Sources** tab
3. **Is your app component listed?**
   - If YES: Good, move to next step
   - If NO: This is likely the problem!

**To fix Trusted Sources:**
1. Click **"Add Trusted Source"**
2. Select your **app component** from the dropdown
3. Click **"Add Trusted Source"**
4. **Save**

**Alternative (for testing only):**
- Add `0.0.0.0/0` to allow all IPs
- Less secure but works for testing

### Step 4: Check Build Command

1. **App** → **Settings** → **General**
2. **Build Command** should be:
   ```
   pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
   ```
3. **Make sure it includes:** `python manage.py migrate --noinput`

### Step 5: Redeploy and Check

1. **Save all changes**
2. **Redeploy** (push commit or manual deploy)
3. **Check Build Logs:**
   - Should see: "Running migrations..."
   - Should see: "OK" for each migration
   - Should NOT see: "connection timeout" or errors

4. **Check Health Endpoint:**
   - Visit: `https://your-app.ondigitalocean.app/health/`
   - What does it show? Share the response

## Common Problems and Solutions

### Problem 1: DATABASE_URL Not Set

**Symptom:** Health endpoint shows `"has_database_url": false`

**Fix:**
- Get connection string from Database → Connection Details
- Add it manually to Environment Variables
- Include `?sslmode=require` at the end

### Problem 2: Trusted Sources Not Configured

**Symptom:** Connection timeout errors

**Fix:**
- Database → Trusted Sources
- Add your app component
- Save and redeploy

### Problem 3: Wrong Connection String Format

**Symptom:** Various connection errors

**Fix:**
- Get fresh connection string from Database → Connection Details
- Use the **URI** format (not individual fields)
- Should include: `postgresql://`, host, port (25060), database name, `?sslmode=require`

### Problem 4: Build Command Missing Migrations

**Symptom:** "relation does not exist" errors

**Fix:**
- App → Settings → General
- Build Command must include: `python manage.py migrate --noinput`

## Diagnostic Questions

To help you fix this, I need to know:

1. **Is DATABASE_URL set?**
   - Check App → Settings → Environment Variables
   - Is `DATABASE_URL` listed?

2. **What does the health endpoint show?**
   - Visit `/health/`
   - What's the response? (especially the "database" section)

3. **What do build logs show?**
   - Check latest deployment → Build Logs
   - Any errors? What do they say?

4. **Are Trusted Sources configured?**
   - Database → Trusted Sources
   - Is your app listed?

5. **What's the database component status?**
   - App → Components tab
   - Is database component listed?
   - What's its status?

## Quick Test

After making changes:

1. **Redeploy**
2. **Visit `/health/`** endpoint
3. **Check the response:**
   - `"connection": "success"` = Working! ✅
   - `"connection": "failed"` = Still broken, check the error message

Share what the `/health/` endpoint shows and I can give you the exact fix!
