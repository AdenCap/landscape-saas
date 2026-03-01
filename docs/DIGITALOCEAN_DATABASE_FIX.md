# DigitalOcean Database Connection Fix

## Common Issues with DigitalOcean PostgreSQL

### 1. SSL Required

DigitalOcean managed databases **require SSL**. Make sure your connection string includes SSL:

**Correct format:**
```
postgresql://username:password@host:port/database?sslmode=require
```

**Or add to connection string:**
```
postgresql://username:password@host:port/database?sslmode=require&sslcert=&sslkey=&sslrootcert=
```

### 2. Get Your Connection String from DigitalOcean

1. Go to DigitalOcean Dashboard
2. Click **Databases** in left sidebar
3. Click on your database cluster
4. Click **Connection Details**
5. Copy the **Connection String** (URI format)
6. It should look like:
   ```
   postgresql://doadmin:password@db-host:25060/defaultdb?sslmode=require
   ```

### 3. Common Connection String Issues

**Problem: Missing SSL parameter**
- DigitalOcean requires `sslmode=require`
- Add `?sslmode=require` to the end of your connection string

**Problem: Wrong port**
- DigitalOcean uses port **25060** (not 5432)
- Make sure your connection string uses the correct port

**Problem: Password with special characters**
- If password has `@`, `#`, `%`, etc., URL encode them:
  - `@` → `%40`
  - `#` → `%23`
  - `%` → `%25`
- Or reset password to one without special characters

### 4. Trusted Sources (Firewall)

DigitalOcean databases have a firewall. Make sure your app server IP is allowed:

1. Go to Database → **Trusted Sources**
2. Add your app server's IP address
3. Or add `0.0.0.0/0` to allow all (less secure, but works for testing)

### 5. Database User Permissions

Make sure your database user has proper permissions:

1. Connect to database (via DigitalOcean console or psql)
2. Run:
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE your_database_name TO your_username;
   ```

### 6. Test Connection Locally

If you have the connection string, test it:

```bash
# Install psql if needed
# macOS: brew install postgresql
# Linux: apt-get install postgresql-client

# Test connection
psql "postgresql://user:pass@host:25060/db?sslmode=require"
```

### 7. Environment Variable Setup

In your DigitalOcean App Platform:

1. Go to your App → **Settings** → **App-Level Environment Variables**
2. Add:
   - **Key:** `DATABASE_URL`
   - **Value:** Your full connection string with `?sslmode=require`
   - **Scope:** Runtime (or All)

3. **Redeploy** after adding the variable

### 8. Check Build Logs

After deployment, check build logs for:

- Database connection errors
- Migration errors
- "Using persistent database: django.db.backends.postgresql" (good sign)

## Step-by-Step Fix

### Step 1: Get Connection String

1. DigitalOcean Dashboard → Databases → Your database
2. Connection Details → Copy URI connection string
3. Should include: `?sslmode=require`

### Step 2: Set Environment Variable

1. DigitalOcean App Platform → Your App → Settings
2. App-Level Environment Variables
3. Add `DATABASE_URL` with the connection string
4. Make sure it includes `?sslmode=require`

### Step 3: Check Trusted Sources

1. Database → Trusted Sources
2. Add your app's IP or `0.0.0.0/0` (for testing)

### Step 4: Redeploy

1. Save environment variable
2. Trigger a new deployment
3. Check logs for errors

### Step 5: Verify

1. Check deployment logs
2. Should see: "Configured PostgreSQL database: ..."
3. Should NOT see: "sqlite3" or "CRITICAL" warnings
4. Try accessing the app

## Common Error Messages

### "could not connect to server"

**Causes:**
- Wrong host/port
- Firewall blocking (check Trusted Sources)
- Database not running

**Fix:**
- Verify connection string from DigitalOcean dashboard
- Check Trusted Sources includes your app IP
- Verify database is running

### "password authentication failed"

**Causes:**
- Wrong password
- Password needs URL encoding

**Fix:**
- Reset password in DigitalOcean
- Update DATABASE_URL
- URL encode special characters

### "SSL connection required"

**Causes:**
- Missing `sslmode=require` in connection string

**Fix:**
- Add `?sslmode=require` to end of DATABASE_URL
- DigitalOcean requires SSL

### "database does not exist"

**Causes:**
- Wrong database name

**Fix:**
- Check database name in DigitalOcean dashboard
- Usually `defaultdb` for new databases
- Or the name you created

## Still Not Working?

1. **Check exact error** in deployment logs
2. **Verify connection string** format
3. **Test connection** with psql locally
4. **Check Trusted Sources** in database settings
5. **Verify SSL** is in connection string

## Quick Test

Run this to test your connection string locally:

```bash
# Set your connection string
export DATABASE_URL="postgresql://user:pass@host:25060/db?sslmode=require"

# Test with Django
python manage.py dbshell

# Or test with psql
psql "$DATABASE_URL"
```

If this works locally but not in deployment, check:
- Environment variable is set correctly in DigitalOcean
- Trusted Sources includes deployment IPs
- Connection string is exactly the same
