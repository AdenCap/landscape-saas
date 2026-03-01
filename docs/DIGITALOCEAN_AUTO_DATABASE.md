# DigitalOcean Auto-Connected Database Setup

## How DigitalOcean Auto-Connection Works

When you add a database as a **component** to your app in DigitalOcean:

1. DigitalOcean automatically creates the database
2. DigitalOcean automatically sets `DATABASE_URL` environment variable
3. DigitalOcean automatically configures Trusted Sources
4. Your app should connect automatically

## Verify It's Set Up Correctly

### Step 1: Check Database Component

1. **DigitalOcean Dashboard** → Your App
2. **Components** tab
3. You should see a **Database** component listed
4. Status should be **"Connected"** or **"Running"**

### Step 2: Verify DATABASE_URL is Set

1. **App** → **Settings** → **App-Level Environment Variables**
2. Look for `DATABASE_URL`
3. It should be **automatically set** by DigitalOcean
4. Value should be a PostgreSQL connection string

**If DATABASE_URL is NOT there:**
- The database component might not be properly connected
- See "Troubleshooting" below

### Step 3: Check Trusted Sources

1. **Databases** → Your database
2. **Trusted Sources** tab
3. Should show your app component listed
4. If not, add it manually (see below)

### Step 4: Verify Connection String Format

The auto-set `DATABASE_URL` should:
- Start with `postgresql://`
- Include host, port (usually 25060), database name
- Include `?sslmode=require` at the end

**Example:**
```
postgresql://doadmin:password@db-host:25060/defaultdb?sslmode=require
```

## If DATABASE_URL is Not Auto-Set

Sometimes DigitalOcean doesn't automatically set it. Here's how to fix:

### Option 1: Reconnect Database Component

1. **App** → **Components** tab
2. Find your Database component
3. Click **Settings** or **Edit**
4. Make sure it's connected to your app
5. Save and redeploy

### Option 2: Set DATABASE_URL Manually

1. **Databases** → Your database
2. **Connection Details** tab
3. Copy the **URI** connection string
4. **App** → **Settings** → **Environment Variables**
5. Add:
   - **Key:** `DATABASE_URL`
   - **Value:** The connection string (should include `?sslmode=require`)
   - **Scope:** Run Time
6. Save and redeploy

## Verify It's Working

### Check 1: Environment Variables

1. **App** → **Settings** → **Environment Variables**
2. `DATABASE_URL` should be listed
3. Value should be a PostgreSQL connection string

### Check 2: Build Logs

After deployment, check **Build Logs**:
- Should see: "Running migrations..."
- Should see: "OK" for each migration
- Should NOT see: "connection timeout" or errors

### Check 3: Health Endpoint

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

### Check 4: Runtime Logs

**App** → **Runtime Logs**:
- Should see: "Configured PostgreSQL database: ..."
- Should see: "Database connection test successful"
- Should NOT see: "sqlite3" or connection errors

## Common Issues

### Issue 1: DATABASE_URL Not Set

**Symptoms:**
- Environment variables don't show DATABASE_URL
- App still using SQLite

**Fix:**
1. Check Components tab - is database listed?
2. If yes, try disconnecting and reconnecting
3. If no, add database as component
4. Or set DATABASE_URL manually (see above)

### Issue 2: Trusted Sources Not Configured

**Symptoms:**
- Connection timeout
- "could not connect to server"

**Fix:**
1. Database → Trusted Sources
2. Should show your app component
3. If not, add it manually:
   - Click "Add Trusted Source"
   - Select your app from dropdown
   - Save

### Issue 3: Wrong Connection String

**Symptoms:**
- Connection errors
- Authentication failures

**Fix:**
1. Get fresh connection string from Database → Connection Details
2. Update DATABASE_URL in app settings
3. Make sure it includes `?sslmode=require`
4. Redeploy

## Step-by-Step: Ensure Everything is Connected

### Step 1: Verify Database Component

1. **App** → **Components** tab
2. Database should be listed
3. Status should be "Connected" or "Running"

**If not listed:**
- Click "Add Component" → "Database" → "PostgreSQL"
- Choose plan
- DigitalOcean will create and connect it

### Step 2: Verify DATABASE_URL

1. **App** → **Settings** → **Environment Variables**
2. Look for `DATABASE_URL`
3. Should be automatically set

**If not there:**
- Get connection string from Database → Connection Details
- Add `DATABASE_URL` manually
- Include `?sslmode=require` at the end

### Step 3: Verify Trusted Sources

1. **Databases** → Your database
2. **Trusted Sources** tab
3. Should show your app component

**If not there:**
- Click "Add Trusted Source"
- Select your app from dropdown
- Save

### Step 4: Verify Build Command

1. **App** → **Settings** → **General**
2. **Build Command** should include migrations:
   ```
   pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
   ```

### Step 5: Test

1. **Deploy** (or push a commit)
2. **Check Build Logs** - should see migrations running
3. **Check Health Endpoint** - `/health/` should show success
4. **Create test data** - customer, invoice, etc.
5. **Deploy again** - data should persist

## Quick Checklist

- [ ] Database component is listed in App → Components
- [ ] DATABASE_URL is set in Environment Variables (auto or manual)
- [ ] Trusted Sources includes your app
- [ ] Build command includes `migrate`
- [ ] Health endpoint shows PostgreSQL connection success
- [ ] Data persists after deployments

## Still Not Working?

1. **Check Components tab:**
   - Is database component there?
   - Is it connected?

2. **Check Environment Variables:**
   - Is DATABASE_URL set?
   - What does the value look like?

3. **Check Trusted Sources:**
   - Is your app listed?
   - If not, add it

4. **Check Build Logs:**
   - What error do you see?
   - Are migrations running?

5. **Check Health Endpoint:**
   - Visit `/health/`
   - What does it show?

Share what you find and I can help fix the specific issue!
