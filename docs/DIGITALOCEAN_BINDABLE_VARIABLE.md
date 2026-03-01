# DigitalOcean Bindable Variable Fix

## The Issue

DigitalOcean App Platform uses **bindable variables** like `${db.DATABASE_URL}` that get automatically resolved to `DATABASE_URL` at runtime. If you're not seeing `DATABASE_URL` in your environment variables, you might need to use the bindable variable format.

## How DigitalOcean Bindable Variables Work

When you add a database as a **component** to your app:

1. DigitalOcean creates a bindable variable: `${db.DATABASE_URL}`
2. This gets automatically resolved to `DATABASE_URL` at runtime
3. Your app should use `DATABASE_URL` (the resolved value)

## Verify You're Using the Right Variable

### Step 1: Check Environment Variables

1. **App** → **Settings** → **App-Level Environment Variables**
2. Look for:
   - `DATABASE_URL` (the resolved value) - **This is what we use**
   - OR `${db.DATABASE_URL}` (the bindable variable) - DigitalOcean format

### Step 2: If You See `${db.DATABASE_URL}`

**Option A: Let DigitalOcean Resolve It (Recommended)**

DigitalOcean should automatically resolve `${db.DATABASE_URL}` to `DATABASE_URL` at runtime. Our code looks for `DATABASE_URL`, which should work.

**Option B: Use the Bindable Variable Directly**

If DigitalOcean isn't resolving it automatically:

1. **App** → **Settings** → **Environment Variables**
2. **Add Variable:**
   - **Key:** `DATABASE_URL`
   - **Value:** `${db.DATABASE_URL}` (copy exactly as shown)
   - **Scope:** Run Time
3. DigitalOcean will resolve `${db.DATABASE_URL}` to the actual connection string at runtime

### Step 3: Get the Actual Connection String

If bindable variables aren't working:

1. **Databases** → Your database
2. **Connection Details** tab
3. **Copy the URI connection string** (the actual value)
4. **App** → **Settings** → **Environment Variables**
5. **Add Variable:**
   - **Key:** `DATABASE_URL`
   - **Value:** The actual connection string (not `${db.DATABASE_URL}`)
   - **Scope:** Run Time
6. **Save**

## Important: Don't Drop Tables

Our code does NOT drop or recreate tables. We only:
- Run migrations (`python manage.py migrate`) - this adds new tables/columns, never drops
- Never run `DROP DATABASE` or `DROP TABLE`
- Never run `syncdb` or `flush`

This is safe - migrations only add/modify, never delete existing data.

## Verify Database Component is Bound

1. **App** → **Components** tab
2. **Database component** should be listed
3. Status should be **"Connected"** or **"Bound"**
4. If not connected, click **Settings** and ensure it's bound to your app

## Quick Fix Checklist

- [ ] Database component is listed in Components tab
- [ ] Component status is "Connected" or "Bound"
- [ ] `DATABASE_URL` is in Environment Variables (either as resolved value or `${db.DATABASE_URL}`)
- [ ] Trusted Sources includes your app
- [ ] Build command includes `migrate` (not `syncdb` or `flush`)
- [ ] No DROP statements in your code

## Still Not Working?

1. **Check Components tab:**
   - Is database component there?
   - Is it bound/connected?

2. **Check Environment Variables:**
   - Do you see `DATABASE_URL` or `${db.DATABASE_URL}`?
   - What's the value? (first 50 chars without password)

3. **Try setting it manually:**
   - Get connection string from Database → Connection Details
   - Add as `DATABASE_URL` (not `${db.DATABASE_URL}`)
   - Use the actual connection string value

4. **Check Trusted Sources:**
   - Database → Trusted Sources
   - Is your app listed?

5. **Check Health Endpoint:**
   - Visit `/health/`
   - What does it show?

Share what you find and I can help fix the specific issue!
