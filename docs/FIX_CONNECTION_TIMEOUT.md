# Fix: Database Connection Timeout on DigitalOcean

## The Problem

"Database connection timeout" means your app can't reach the database. This is usually a **firewall/network** issue.

## Quick Fix (2 minutes)

### Step 1: Check Trusted Sources (Most Common Fix)

DigitalOcean databases have a firewall. Your app's IP must be allowed:

1. **Go to DigitalOcean Dashboard**
2. **Click Databases** → Your database
3. **Click "Trusted Sources"** tab
4. **Add your app:**
   - Option A: Add your app component (if using App Platform)
     - Click "Add Trusted Source"
     - Select your app from the dropdown
   - Option B: Add IP manually
     - Click "Add Trusted Source"
     - Enter `0.0.0.0/0` (allows all IPs - for testing)
     - Or add your specific app server IP
5. **Save**

### Step 2: Verify Connection String

1. **Get fresh connection string:**
   - Database → Connection Details
   - Copy the **URI** connection string
   - Should include `?sslmode=require`

2. **Set in App Platform:**
   - App → Settings → App-Level Environment Variables
   - Update `DATABASE_URL` with the exact string from DigitalOcean
   - Make sure it includes `?sslmode=require`

3. **Redeploy**

### Step 3: If Using App Platform Database Component

If you added the database as a component to your app:

1. **Check it's connected:**
   - App → Components tab
   - Database component should be listed
   - Should show "Connected"

2. **Verify DATABASE_URL is auto-set:**
   - App → Settings → Environment Variables
   - `DATABASE_URL` should be automatically set
   - If not, add it manually from Connection Details

## Detailed Troubleshooting

### Issue 1: Trusted Sources Not Configured

**Symptoms:**
- Connection timeout
- "could not connect to server"
- Build fails during migrations

**Fix:**
1. Database → Trusted Sources
2. Add your app component OR
3. Add `0.0.0.0/0` (allows all - for testing)
4. Save and redeploy

### Issue 2: Wrong Connection String

**Symptoms:**
- Connection timeout
- Wrong host/port

**Fix:**
1. Get connection string from Database → Connection Details
2. Use the **URI** format (not individual fields)
3. Should look like: `postgresql://user:pass@host:25060/db?sslmode=require`
4. Port should be **25060** (DigitalOcean's port)
5. Update `DATABASE_URL` in app settings
6. Redeploy

### Issue 3: Database Not Running

**Symptoms:**
- Connection timeout
- Database status shows as stopped

**Fix:**
1. Check Database → Overview
2. Status should be "Online"
3. If stopped, start it
4. Wait a few minutes for it to be ready

### Issue 4: Network Issues

**Symptoms:**
- Intermittent timeouts
- Works sometimes, fails other times

**Fix:**
1. Check database region matches app region (if possible)
2. Verify database is in same project/account
3. Check for any network restrictions

## Step-by-Step Fix

### Method 1: Using App Platform Database Component (Easiest)

1. **In your App:**
   - Go to **Components** tab
   - Click **Add Component** → **Database**
   - Choose **PostgreSQL**
   - Select plan
   - DigitalOcean will automatically:
     - Create the database
     - Set `DATABASE_URL` environment variable
     - Configure Trusted Sources

2. **Redeploy:**
   - Should work automatically

### Method 2: Using Separate Database (Manual Setup)

1. **Create Database:**
   - DigitalOcean → Databases → Create Database
   - Choose PostgreSQL
   - Select region (same as app if possible)
   - Create

2. **Get Connection String:**
   - Database → Connection Details
   - Copy **URI** connection string
   - Should include `?sslmode=require`

3. **Set Trusted Sources:**
   - Database → Trusted Sources
   - Add your app component OR
   - Add `0.0.0.0/0` (for testing)

4. **Set Environment Variable:**
   - App → Settings → Environment Variables
   - Add `DATABASE_URL` with the connection string
   - Make sure it includes `?sslmode=require`

5. **Redeploy**

## Verify It's Fixed

### Check 1: Build Logs

After redeploy, check Build Logs:
- Should see: "Running migrations..."
- Should see: "OK" for each migration
- Should NOT see: "connection timeout" or "could not connect"

### Check 2: Health Endpoint

Visit: `https://your-app.ondigitalocean.app/health/`

Should show:
```json
{
  "status": "ok",
  "database": {
    "connection": "success",
    "engine": "django.db.backends.postgresql"
  }
}
```

### Check 3: Runtime Logs

App → Runtime Logs:
- Should see: "Configured PostgreSQL database: ..."
- Should see: "Database connection test successful"
- Should NOT see: "connection timeout"

## Common Mistakes

❌ **Wrong:** Connection string without `?sslmode=require`
✅ **Right:** `postgresql://user:pass@host:25060/db?sslmode=require`

❌ **Wrong:** Trusted Sources empty
✅ **Right:** Trusted Sources includes your app or `0.0.0.0/0`

❌ **Wrong:** Using wrong port (5432 instead of 25060)
✅ **Right:** Port 25060 (DigitalOcean's port)

❌ **Wrong:** Connection string in wrong format
✅ **Right:** Full URI format from Connection Details

## Still Getting Timeout?

1. **Double-check Trusted Sources:**
   - Must include your app or `0.0.0.0/0`
   - Save after adding

2. **Verify connection string:**
   - Get fresh one from DigitalOcean
   - Copy exactly as shown
   - Include `?sslmode=require`

3. **Check database status:**
   - Should be "Online"
   - Not "Stopped" or "Maintenance"

4. **Try adding app component:**
   - If using separate database, try adding it as a component instead
   - DigitalOcean handles connection automatically

5. **Check regions:**
   - Database and app in same region helps
   - Different regions can cause timeouts

## Quick Checklist

- [ ] Trusted Sources includes your app or `0.0.0.0/0`
- [ ] DATABASE_URL is set correctly
- [ ] Connection string includes `?sslmode=require`
- [ ] Port is 25060 (DigitalOcean's port)
- [ ] Database status is "Online"
- [ ] Redeployed after making changes
