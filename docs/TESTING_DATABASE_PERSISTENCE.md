# Testing Database Persistence

## Quick Test (5 minutes)

### Step 1: Check Health Endpoint

Visit your app's health endpoint:
```
https://your-app.ondigitalocean.app/health/
```

**What to look for:**
- ✅ `"status": "ok"` - Good!
- ✅ `"database": {"connection": "success"}` - Database connected!
- ✅ `"database": {"engine": "django.db.backends.postgresql"}` - Using PostgreSQL!
- ❌ `"database": {"connection": "failed"}` - Connection issue
- ❌ `"database": {"engine": "django.db.backends.sqlite3"}` - Still using SQLite (bad!)

### Step 2: Create Test Data

1. **Log into your app**
2. **Create test data:**
   - Create a customer
   - Create an invoice
   - Add an employee
   - Create a job

3. **Verify it's there:**
   - Check customers list - should see your test customer
   - Check invoices list - should see your test invoice
   - Check employees list - should see your test employee

### Step 3: Test Persistence (The Critical Test)

1. **Make a new deployment:**
   - Push a commit to trigger deployment
   - Or manually trigger redeploy in DigitalOcean
   - Wait for deployment to complete

2. **Check if data is still there:**
   - Log back into your app
   - Check customers - **should still see your test customer**
   - Check invoices - **should still see your test invoice**
   - Check employees - **should still see your test employee**

3. **If data is still there:** ✅ **SUCCESS!** Your database is persistent.

4. **If data is gone:** ❌ Still using SQLite or database not connected properly.

## Detailed Testing Steps

### Test 1: Database Connection

**Method A: Health Endpoint**
```
Visit: https://your-app.ondigitalocean.app/health/
```

Look for:
```json
{
  "status": "ok",
  "database": {
    "connection": "success",
    "engine": "django.db.backends.postgresql"
  }
}
```

**Method B: Check Logs**
1. DigitalOcean → Your App → Runtime Logs
2. Look for: "Configured PostgreSQL database: ..."
3. Should NOT see: "sqlite3" or "CRITICAL" warnings

### Test 2: Create and Verify Data

1. **Create a business** (if you don't have one):
   - Sign up or log in
   - Create your business

2. **Create test data:**
   - Go to Clients → Add a customer named "Test Customer"
   - Go to Invoices → Create an invoice for "Test Customer"
   - Go to Employees → Add an employee named "Test Employee"
   - Go to Jobs → Create a job

3. **Verify data exists:**
   - Check each list page
   - All test data should be visible

### Test 3: Persistence Test (Most Important)

This is the test that matters - does data survive deployments?

1. **Before deployment:**
   - Note what data you have (customers, invoices, etc.)
   - Count them if helpful

2. **Trigger a deployment:**
   - Make a small change (add a comment to a file)
   - Push to git
   - Or manually redeploy in DigitalOcean
   - Wait for deployment to complete (2-5 minutes)

3. **After deployment:**
   - Log back into your app
   - Check all your data:
     - Customers list - should have same customers
     - Invoices list - should have same invoices
     - Employees list - should have same employees
     - Jobs list - should have same jobs

4. **Result:**
   - ✅ **Data still there** = Database is persistent! Success!
   - ❌ **Data gone** = Still using SQLite or database not connected

### Test 4: Multiple Deployments

To be extra sure, test multiple times:

1. Create more test data
2. Deploy again
3. Check data persists
4. Repeat 2-3 times

If data persists through multiple deployments, you're good!

## What Success Looks Like

### ✅ Success Indicators:

1. **Health endpoint shows:**
   ```json
   {
     "status": "ok",
     "database": {
       "connection": "success",
       "engine": "django.db.backends.postgresql"
     }
   }
   ```

2. **Logs show:**
   - "Configured PostgreSQL database: ..."
   - "Database connection test successful"
   - NO "sqlite3" mentions
   - NO "CRITICAL" warnings about SQLite

3. **Data persists:**
   - Create data → Deploy → Data still there ✅

### ❌ Failure Indicators:

1. **Health endpoint shows:**
   ```json
   {
     "status": "error",
     "database": {
       "connection": "failed",
       "engine": "django.db.backends.sqlite3"
     }
   }
   ```

2. **Logs show:**
   - "sqlite3" database
   - "CRITICAL: Using SQLite in production"
   - Connection errors

3. **Data doesn't persist:**
   - Create data → Deploy → Data gone ❌

## Troubleshooting Failed Tests

### If Health Endpoint Shows Connection Failed

1. **Check DATABASE_URL:**
   - Is it set in DigitalOcean?
   - Does it include `?sslmode=require`?
   - Is the format correct?

2. **Check Trusted Sources:**
   - Database → Trusted Sources
   - Add your app's IP or `0.0.0.0/0`

3. **Check connection string:**
   - Get fresh connection string from DigitalOcean
   - Verify password is correct
   - Make sure port is 25060

### If Still Using SQLite

1. **Verify DATABASE_URL is set:**
   - Check App-Level Environment Variables
   - Make sure it's for "Run Time" scope
   - Redeploy after setting

2. **Check connection string format:**
   - Should start with `postgresql://`
   - Should include host, port, database name
   - Should end with `?sslmode=require`

### If Data Doesn't Persist

1. **Check database engine:**
   - Health endpoint should show PostgreSQL
   - Logs should show PostgreSQL

2. **Verify migrations ran:**
   - Check build logs
   - Should see "Running migrations..."
   - Should see "OK" for each migration

3. **Check if using correct database:**
   - Make sure you're not accidentally using a test database
   - Verify DATABASE_URL points to production database

## Quick Checklist

- [ ] Health endpoint shows PostgreSQL and connection success
- [ ] Logs show "Configured PostgreSQL database"
- [ ] Can create data (customers, invoices, etc.)
- [ ] Data persists after deployment
- [ ] Data persists after multiple deployments
- [ ] No "sqlite3" in logs
- [ ] No "CRITICAL" warnings about SQLite

## Still Having Issues?

1. **Share health endpoint response:**
   - Visit `/health/`
   - Copy the JSON response
   - Share it (remove any sensitive info)

2. **Share error messages:**
   - From Runtime Logs
   - Any "ERROR" or "CRITICAL" messages

3. **Check these:**
   - DATABASE_URL format
   - Trusted Sources in database
   - Build command includes migrations
