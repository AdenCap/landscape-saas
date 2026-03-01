# Troubleshooting Database Connection Errors

## Common Errors After Setting DATABASE_URL

### Error: "could not connect to server"

**Causes:**
- Wrong host/port in connection string
- Database doesn't exist yet
- Network/firewall blocking connection
- SSL required but not enabled

**Solutions:**
1. **Check connection string format:**
   ```
   postgresql://username:password@host:port/database_name
   ```

2. **For Supabase:**
   - Use **Session mode** (port 6543) for serverless
   - Use **Direct connection** (port 5432) for traditional servers
   - Make sure password is URL-encoded (special characters)

3. **Verify database exists:**
   - Log into your database provider's dashboard
   - Confirm the database was created
   - Check the exact database name

4. **Check SSL:**
   - Most cloud databases require SSL
   - Connection string should include `?sslmode=require` if needed
   - Supabase handles this automatically

### Error: "password authentication failed"

**Causes:**
- Wrong password in connection string
- Password needs URL encoding
- User doesn't have permissions

**Solutions:**
1. **Reset password:**
   - Go to your database provider's dashboard
   - Reset the database password
   - Update `DATABASE_URL` with new password

2. **URL encode special characters:**
   - If password has `@`, `#`, `%`, etc., encode them
   - `@` becomes `%40`
   - `#` becomes `%23`
   - Or use a password without special characters

3. **Check user permissions:**
   - User needs CREATE, SELECT, INSERT, UPDATE, DELETE permissions
   - For Supabase: `postgres` user has all permissions

### Error: "database does not exist"

**Causes:**
- Database name is wrong
- Database wasn't created yet

**Solutions:**
1. **Create the database:**
   ```sql
   CREATE DATABASE your_database_name;
   ```

2. **Or use the default:**
   - Supabase: Use `postgres` as database name
   - Most providers: Database name is set when you create it

### Error: "relation does not exist" or "table does not exist"

**Causes:**
- Migrations haven't run
- Database is empty

**Solutions:**
1. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

2. **Check build logs:**
   - Your build should run `python manage.py migrate --noinput`
   - Check deployment logs to see if migrations ran
   - If they failed, fix the error and redeploy

### Error: "connection timeout" or "connection refused"

**Causes:**
- Wrong host/port
- Firewall blocking
- Database not accessible from your platform

**Solutions:**
1. **Check host and port:**
   - Supabase Session mode: port 6543
   - Supabase Direct: port 5432
   - Other providers: usually 5432

2. **Check network access:**
   - Some databases only allow connections from specific IPs
   - Check your database provider's network settings
   - For serverless (Vercel), you may need to allow all IPs

3. **Use connection pooling:**
   - For Supabase: Use Session mode (port 6543) - it's a pooler
   - For other providers: Check if they offer a pooler

### Error: "SSL connection required"

**Causes:**
- Database requires SSL but connection string doesn't specify it

**Solutions:**
1. **Add SSL parameter:**
   ```
   postgresql://user:pass@host:port/db?sslmode=require
   ```

2. **For Supabase:**
   - Session mode handles SSL automatically
   - Direct connection may need `?sslmode=require`

## Quick Diagnostic Steps

### 1. Check Your Connection String

Format should be:
```
postgresql://[user]:[password]@[host]:[port]/[database]
```

**Example (Supabase Session mode):**
```
postgresql://postgres:your_password@db.xxxxx.supabase.co:6543/postgres
```

### 2. Test Connection Locally

If you have the connection string locally:
```bash
# Test with psql (if installed)
psql "postgresql://user:pass@host:port/db"

# Or test with Python
python scripts/verify_database.py
```

### 3. Check Deployment Logs

Look for:
- Database connection errors
- Migration errors
- "Using persistent database: django.db.backends.postgresql" (good sign)
- Any "CRITICAL" or "ERROR" messages about database

### 4. Verify Environment Variable

- Is `DATABASE_URL` set in your platform's dashboard?
- Is it set for the correct environment (Production, Preview, etc.)?
- Did you redeploy after setting it?

## Common Fixes by Platform

### Vercel
1. Go to Project → Settings → Environment Variables
2. Add `DATABASE_URL` (make sure it's for Production)
3. Redeploy
4. Check Functions logs for errors

### Railway
1. Go to Project → Variables
2. Add `DATABASE_URL`
3. Redeploy
4. Check Deploy logs

### Render
1. Go to Environment → Environment Variables
2. Add `DATABASE_URL`
3. Manual Deploy
4. Check Logs

## Still Having Issues?

1. **Check the exact error message** - share it and I can help
2. **Check deployment logs** - look for database-related errors
3. **Verify connection string** - test it with a database client
4. **Check database provider status** - make sure their service is up

## Getting Help

Share:
- The exact error message
- Your platform (Vercel/Railway/Render/etc.)
- Whether you're using Supabase or another provider
- Any relevant log output
