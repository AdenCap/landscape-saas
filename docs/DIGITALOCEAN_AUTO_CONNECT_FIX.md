# Fix: DigitalOcean Auto-Connected Database Not Working

## The Situation

You added a database as a **component** to your app in DigitalOcean. DigitalOcean should automatically:
- Set `DATABASE_URL` environment variable
- Configure Trusted Sources
- Connect everything

But it's still not working. Here's how to fix it.

## Step-by-Step Fix

### Step 1: Verify Database Component is Connected

1. **DigitalOcean Dashboard** → Your App
2. **Components** tab
3. Look for **Database** component
4. Status should be **"Connected"** or **"Running"**

**If not there:**
- Click **"Add Component"** → **"Database"** → **"PostgreSQL"**
- Choose a plan
- DigitalOcean will create and connect it

### Step 2: Check DATABASE_URL is Set

1. **App** → **Settings** → **App-Level Environment Variables**
2. Scroll down and look for **`DATABASE_URL`**
3. It should be **automatically set** by DigitalOcean

**If DATABASE_URL is NOT there:**

DigitalOcean sometimes doesn't set it automatically. Fix it:

1. **Go to Databases** → Your database
2. **Connection Details** tab
3. Copy the **URI** connection string
4. **Go back to App** → **Settings** → **Environment Variables**
5. Click **"Add Variable"**:
   - **Key:** `DATABASE_URL`
   - **Value:** Paste the connection string
   - **Scope:** Run Time
6. **Important:** Make sure it includes `?sslmode=require` at the end
   - If it doesn't, add it: `...?sslmode=require`
7. **Save**

### Step 3: Verify Trusted Sources

1. **Databases** → Your database
2. **Trusted Sources** tab
3. Your app component should be listed

**If your app is NOT listed:**

1. Click **"Add Trusted Source"**
2. Select your **app component** from the dropdown
3. Click **"Add Trusted Source"**
4. **Save**

**Alternative (for testing):**
- Add `0.0.0.0/0` to allow all IPs (less secure, but works for testing)

### Step 4: Verify Build Command

1. **App** → **Settings** → **General**
2. **Build Command** should be:
   ```
   pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
   ```
3. Make sure it includes `migrate --noinput`

### Step 5: Redeploy

1. **Save all changes**
2. **Trigger a new deployment:**
   - Push a commit to git, OR
   - Click **"Deploy"** in DigitalOcean
3. **Wait for deployment** to complete

### Step 6: Check It's Working

1. **Check Build Logs:**
   - Should see: "Running migrations..."
   - Should see: "OK" for each migration
   - Should NOT see: "connection timeout" or errors

2. **Check Health Endpoint:**
   - Visit: `https://your-app.ondigitalocean.app/health/`
   - Should show: `"connection": "success"` and `"postgresql"`

3. **Check Runtime Logs:**
   - Should see: "Configured PostgreSQL database: ..."
   - Should see: "Database connection test successful"

## Common Issues

### Issue 1: DATABASE_URL Not Auto-Set

**Symptom:** Environment Variables doesn't show DATABASE_URL

**Fix:**
- Get connection string from Database → Connection Details
- Add it manually to Environment Variables
- Include `?sslmode=require` at the end

### Issue 2: Connection Timeout

**Symptom:** Build fails with "connection timeout"

**Fix:**
- Check Trusted Sources includes your app
- Add your app component to Trusted Sources
- Or add `0.0.0.0/0` for testing

### Issue 3: SSL Error

**Symptom:** "SSL connection required" error

**Fix:**
- Make sure DATABASE_URL ends with `?sslmode=require`
- DigitalOcean requires SSL
- The code now auto-adds this if missing, but verify it's there

### Issue 4: Wrong Connection String Format

**Symptom:** Various connection errors

**Fix:**
- Get fresh connection string from Database → Connection Details
- Use the **URI** format (not individual fields)
- Should look like: `postgresql://user:pass@host:25060/db?sslmode=require`

## Quick Verification Checklist

After following the steps above:

- [ ] Database component is listed in Components tab
- [ ] DATABASE_URL is in Environment Variables (check both auto and manual)
- [ ] DATABASE_URL includes `?sslmode=require`
- [ ] Trusted Sources includes your app
- [ ] Build command includes `migrate`
- [ ] Build logs show migrations running successfully
- [ ] Health endpoint shows PostgreSQL connection success
- [ ] Can create data and it persists after deployment

## What I Just Fixed in Code

1. **Auto-add SSL** - Code now automatically adds `?sslmode=require` if missing
2. **Better DigitalOcean detection** - Detects DigitalOcean databases and requires SSL
3. **Better error messages** - Health endpoint shows helpful diagnostics
4. **Check multiple env var names** - Checks DATABASE_URL, POSTGRES_URL, etc.

## Still Not Working?

1. **Check Components tab:**
   - Is database component there?
   - What's its status?

2. **Check Environment Variables:**
   - Is DATABASE_URL set?
   - What does the value look like? (first 50 chars)

3. **Check Trusted Sources:**
   - Is your app listed?
   - If not, add it

4. **Check Build Logs:**
   - What exact error do you see?
   - Copy the full error message

5. **Check Health Endpoint:**
   - Visit `/health/`
   - What does it show?

Share what you find and I can help fix the specific issue!
