# DigitalOcean Server Error - Quick Fix

## Most Common Issue: SSL Required

DigitalOcean managed databases **REQUIRE SSL**. Your connection string must include `?sslmode=require`.

### Fix Steps:

1. **Get your connection string from DigitalOcean:**
   - Go to Databases → Your database
   - Click **Connection Details**
   - Copy the **URI** connection string
   - It should already include `?sslmode=require`

2. **Set in App Platform:**
   - Go to your App → Settings → App-Level Environment Variables
   - Add or update `DATABASE_URL`
   - Make sure it includes `?sslmode=require` at the end
   - Example: `postgresql://user:pass@host:25060/db?sslmode=require`

3. **Check Trusted Sources:**
   - Go to Database → Trusted Sources
   - Make sure your app's IP is allowed
   - Or add `0.0.0.0/0` for testing (less secure)

4. **Verify Build Command includes migrations:**
   - Go to App → Settings → General
   - Build Command should be:
     ```
     pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
     ```

5. **Redeploy:**
   - Save all changes
   - Trigger a new deployment
   - Check logs for errors

## Check Your Logs

After deployment, check the **Runtime Logs** in DigitalOcean:

1. Go to your App → **Runtime Logs** tab
2. Look for:
   - ✅ "Configured PostgreSQL database: ..." (good)
   - ✅ "Using persistent database: django.db.backends.postgresql" (good)
   - ❌ "sqlite3" (bad - not using PostgreSQL)
   - ❌ "could not connect" (connection issue)
   - ❌ "password authentication failed" (wrong password)
   - ❌ "SSL connection required" (missing SSL)

## Common Errors

### "could not connect to server"
- **Fix:** Check Trusted Sources in database settings
- Add your app's IP address

### "password authentication failed"
- **Fix:** Reset password in DigitalOcean
- Update DATABASE_URL with new password
- URL encode special characters if needed

### "SSL connection required"
- **Fix:** Add `?sslmode=require` to DATABASE_URL
- DigitalOcean requires SSL

### "relation does not exist"
- **Fix:** Migrations didn't run
- Make sure build command includes `python manage.py migrate --noinput`

## Still Not Working?

1. **Check the exact error** in Runtime Logs
2. **Verify DATABASE_URL** format (should have `?sslmode=require`)
3. **Check Trusted Sources** includes your app
4. **Verify build command** includes migrations

Share the exact error message from the logs and I can help fix it!
