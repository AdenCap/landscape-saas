# Database Persistence - CRITICAL FOR PRODUCTION

## ⚠️ IMPORTANT: Data Loss Prevention

**SQLite databases are NOT persistent on cloud platforms** (Vercel, Railway, Render, Heroku, etc.). Every time you deploy or the server restarts, **all your data will be lost** if you're using SQLite.

## The Problem

When using SQLite:
- Database file (`db.sqlite3`) is stored in the filesystem
- Cloud platforms use **ephemeral filesystems** (wiped on each deployment)
- Every `git push` → new deployment → **fresh empty database**
- **All customer data, invoices, jobs, etc. are lost**

## The Solution: Use PostgreSQL

You **MUST** use PostgreSQL (or another persistent database) in production.

### Quick Setup Options

#### Option 1: Supabase (Recommended - Free tier available)

1. Go to https://supabase.com
2. Create a new project
3. Go to **Project Settings** → **Database**
4. Copy the **Connection string** (URI format)
5. Use the **Session mode** connection (port 6543) for serverless platforms
6. Set environment variable:
   ```bash
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:6543/postgres
   ```

#### Option 2: Vercel Postgres

1. In Vercel dashboard → Your project → **Storage**
2. Click **Create Database** → **Postgres**
3. Vercel automatically sets `DATABASE_URL`
4. Done!

#### Option 3: Railway Postgres

1. In Railway dashboard → Your project
2. Click **+ New** → **Database** → **PostgreSQL**
3. Railway automatically sets `DATABASE_URL`
4. Done!

#### Option 4: Render Postgres

1. In Render dashboard → **New** → **PostgreSQL**
2. Create database
3. Copy **Internal Database URL**
4. Set as `DATABASE_URL` environment variable

#### Option 5: DigitalOcean Managed Database

1. Create a PostgreSQL database in DigitalOcean
2. Copy connection string
3. Set as `DATABASE_URL` environment variable

### Setting DATABASE_URL

**Format:**
```
postgresql://username:password@host:port/database_name
```

**Example:**
```bash
DATABASE_URL=postgresql://myuser:mypassword@db.example.com:5432/landscape_db
```

**For Supabase (Session mode - recommended for serverless):**
```bash
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:6543/postgres
```

### Verify It's Working

1. Set `DATABASE_URL` in your platform's environment variables
2. Deploy
3. Check logs - you should see: "Using persistent database: django.db.backends.postgresql"
4. Create some test data (invoice, customer, etc.)
5. Make a new deployment
6. **Data should still be there!**

## Migration from SQLite to PostgreSQL

If you have existing data in SQLite:

1. **Export data from SQLite:**
   ```bash
   python manage.py dumpdata > backup.json
   ```

2. **Set up PostgreSQL** (see options above)

3. **Set DATABASE_URL** environment variable

4. **Run migrations on PostgreSQL:**
   ```bash
   python manage.py migrate
   ```

5. **Load data into PostgreSQL:**
   ```bash
   python manage.py loaddata backup.json
   ```

## Development vs Production

- **Development (local):** SQLite is fine - `db.sqlite3` stays on your computer
- **Production (cloud):** **MUST use PostgreSQL** - SQLite will lose data on every deploy

## How to Check Your Current Setup

1. **Check your environment variables:**
   - Look for `DATABASE_URL` in your platform's settings
   - If it's not set, you're using SQLite (BAD for production)

2. **Check Django logs:**
   - Look for database engine in startup logs
   - Should see: `django.db.backends.postgresql` (GOOD)
   - Should NOT see: `django.db.backends.sqlite3` (BAD for production)

3. **Test persistence:**
   - Create test data
   - Deploy new version
   - Check if data is still there

## Troubleshooting

### "Database connection failed"

- Check `DATABASE_URL` is set correctly
- Verify password is correct
- Check database host is accessible
- For Supabase: Use Session mode (port 6543) not Direct connection

### "Still losing data after setting DATABASE_URL"

- Make sure `DATABASE_URL` is set in **production environment** (not just local)
- Redeploy after setting the variable
- Check logs to confirm it's using PostgreSQL
- Verify the database is actually persistent (not a temporary test database)

### "Migrations failing"

- Make sure database exists
- Check database user has CREATE TABLE permissions
- Run migrations manually: `python manage.py migrate`

## Cost

- **Supabase:** Free tier (500MB database, unlimited API requests)
- **Vercel Postgres:** Starts at $20/month
- **Railway:** ~$5/month for small databases
- **Render:** Free tier available, then ~$7/month
- **DigitalOcean:** ~$15/month for managed database

**Free options:** Supabase free tier is generous for most small/medium apps.

## Backup Strategy

Even with PostgreSQL, you should back up regularly:

1. **Automated backups:**
   - Most providers offer automated backups
   - Enable them in your database provider's dashboard

2. **Manual backups:**
   ```bash
   # Export data
   python manage.py dumpdata > backup-$(date +%Y%m%d).json
   
   # Or use pg_dump for PostgreSQL
   pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql
   ```

3. **Store backups off-platform:**
   - Download backups regularly
   - Store in S3, Google Drive, or another service

## Summary

✅ **DO:**
- Use PostgreSQL in production
- Set `DATABASE_URL` environment variable
- Test that data persists after deployments
- Set up automated backups

❌ **DON'T:**
- Use SQLite in production
- Store database files in git
- Deploy without `DATABASE_URL` set
- Assume data will persist without a persistent database

## Need Help?

If you're still losing data:
1. Check `DATABASE_URL` is set
2. Verify it's using PostgreSQL (check logs)
3. Test with a simple deployment
4. Contact your platform's support if database isn't persisting
