# Fix: ${db.DATABASE_URL} Not Working

## The Problem

You see `${db.DATABASE_URL}` in your environment variables, but the database isn't connecting. This is DigitalOcean's **bindable variable** format that should be automatically resolved, but sometimes it isn't.

## The Solution

You need to set `DATABASE_URL` with the **actual connection string value**, not the bindable variable.

### Step 1: Get the Actual Connection String

1. **DigitalOcean Dashboard** → **Databases** → Your database
2. **Connection Details** tab
3. **Copy the URI connection string** (the actual value)
   - Should look like: `postgresql://doadmin:password@host:25060/defaultdb?sslmode=require`
   - This is the **real connection string**, not `${db.DATABASE_URL}`

### Step 2: Set DATABASE_URL with Actual Value

1. **App** → **Settings** → **App-Level Environment Variables**
2. **Find `DATABASE_URL`** (or `${db.DATABASE_URL}`)
3. **Edit it** or **Add new variable:**
   - **Key:** `DATABASE_URL`
   - **Value:** Paste the **actual connection string** from Step 1
   - **NOT** `${db.DATABASE_URL}` - use the real connection string!
   - **Scope:** Run Time
4. **Save**

### Step 3: Verify Format

The connection string should:
- Start with `postgresql://`
- Include username, password, host, port (25060), database name
- End with `?sslmode=require`

**Example:**
```
postgresql://doadmin:your_password@db-host:25060/defaultdb?sslmode=require
```

### Step 4: Check Trusted Sources

1. **Databases** → Your database
2. **Trusted Sources** tab
3. **Add your app component** if not listed
4. **Save**

### Step 5: Redeploy

1. **Save all changes**
2. **Redeploy** (push commit or manual deploy)
3. **Check Build Logs** - should see migrations running successfully
4. **Check Health Endpoint** - `/health/` should show connection success

## Why This Happens

DigitalOcean's bindable variables (`${db.DATABASE_URL}`) are supposed to be automatically resolved to `DATABASE_URL` at runtime. However:

- Sometimes the resolution doesn't happen during build
- Sometimes it's not set correctly
- Sometimes you need to set it manually

**The fix:** Use the actual connection string value instead of the bindable variable.

## Verify It's Working

After setting the actual connection string:

1. **Check Health Endpoint:**
   - Visit `/health/`
   - Should show: `"connection": "success"` and `"postgresql"`

2. **Check Build Logs:**
   - Should see: "Running migrations..."
   - Should see: "OK" for each migration
   - Should NOT see: connection errors

3. **Test Data Persistence:**
   - Create test data (customer, invoice, etc.)
   - Deploy again
   - Data should still be there

## Quick Checklist

- [ ] Got actual connection string from Database → Connection Details
- [ ] Set `DATABASE_URL` with actual value (not `${db.DATABASE_URL}`)
- [ ] Connection string includes `?sslmode=require`
- [ ] Trusted Sources includes your app
- [ ] Redeployed
- [ ] Health endpoint shows success
- [ ] Data persists after deployments

## Still Not Working?

1. **Double-check connection string:**
   - Get fresh one from Database → Connection Details
   - Make sure it's the **URI** format (not individual fields)
   - Verify it includes `?sslmode=require`

2. **Check Trusted Sources:**
   - Must include your app component

3. **Check Health Endpoint:**
   - Visit `/health/`
   - What error does it show?

Share what the `/health/` endpoint shows and I can help fix the specific issue!
