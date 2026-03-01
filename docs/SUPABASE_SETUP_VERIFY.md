# Verify Supabase Database Setup

## Quick Verification

### Step 1: Check DATABASE_URL Format

Your `DATABASE_URL` should look like:
```
postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:6543/postgres
```

**Important for Supabase:**
- Use **Session mode** (port **6543**) for serverless/serverless-like deployments
- Use **Direct connection** (port **5432**) for traditional servers
- The code automatically detects Supabase and enables SSL

### Step 2: Verify Connection String

1. **Supabase Dashboard** → Your project
2. **Settings** → **Database**
3. **Connection string** → **URI**
4. **Copy the Session mode connection** (port 6543) - recommended
5. **Replace `[YOUR-PASSWORD]`** with your actual database password
6. **Set in your platform:**
   - DigitalOcean: App → Settings → Environment Variables → `DATABASE_URL`
   - Should be the full connection string

### Step 3: Test Connection

After setting `DATABASE_URL` and redeploying:

1. **Visit Health Endpoint:**
   ```
   https://your-app.ondigitalocean.app/health/
   ```
   
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

2. **Check Build Logs:**
   - Should see: "Running migrations..."
   - Should see: "OK" for each migration
   - Should see: "Configured PostgreSQL database: db.xxxxx.supabase.co:6543/postgres"

### Step 4: Test Data Persistence

1. **Create test data:**
   - Add a customer
   - Create an invoice
   - Add an employee

2. **Deploy again** (push a commit or manual deploy)

3. **Check if data persists:**
   - Log back in
   - Check customers, invoices, employees
   - **Data should still be there!** ✅

## Supabase-Specific Notes

### Session Mode vs Direct Connection

**Session Mode (Port 6543) - Recommended:**
- Better for serverless/serverless-like platforms
- Connection pooling
- More reliable for DigitalOcean App Platform
- Use this if you're on DigitalOcean App Platform

**Direct Connection (Port 5432):**
- Traditional server connection
- Use if you have a persistent server
- Still works, but Session mode is preferred

### SSL

Supabase requires SSL, but our code automatically enables it when it detects Supabase (checks for "supabase.com" or "supabase.co" in the host).

### Password in Connection String

Make sure you replace `[YOUR-PASSWORD]` in the connection string with your actual Supabase database password.

## Common Issues

### Issue 1: Wrong Port

**Symptom:** Connection errors

**Fix:**
- Use port **6543** (Session mode) for DigitalOcean App Platform
- Use port **5432** (Direct) only for traditional servers

### Issue 2: Password Not Replaced

**Symptom:** Authentication failed

**Fix:**
- Make sure `[YOUR-PASSWORD]` is replaced with actual password
- Password might need URL encoding if it has special characters

### Issue 3: Wrong Database Name

**Symptom:** "database does not exist"

**Fix:**
- Supabase database name is usually `postgres`
- Check your connection string - should end with `/postgres`

## Verify Everything is Working

### Checklist:

- [ ] DATABASE_URL is set with Supabase connection string
- [ ] Using Session mode (port 6543) for DigitalOcean
- [ ] Password is replaced (not `[YOUR-PASSWORD]`)
- [ ] Health endpoint shows PostgreSQL connection success
- [ ] Build logs show migrations running successfully
- [ ] Can create data in the app
- [ ] Data persists after deployment

## Next Steps

1. **Redeploy** with the new DATABASE_URL
2. **Check `/health/`** endpoint - should show success
3. **Create test data** - customer, invoice, employee
4. **Deploy again** - data should persist
5. **If data persists:** ✅ Success! Your database is working!

If you're still having issues, share what the `/health/` endpoint shows and I can help troubleshoot!
