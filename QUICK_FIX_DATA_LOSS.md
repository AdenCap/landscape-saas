# 🚨 URGENT: Fix Data Loss Issue

## The Problem

Your database is being wiped on every deployment because you're using **SQLite** on a platform with an **ephemeral filesystem** (Vercel, Railway, Render, etc.).

**Every `git push` = new deployment = fresh empty database = all data lost**

## Immediate Fix (5 minutes)

### Step 1: Set Up PostgreSQL

Choose one:

#### Option A: Supabase (Free, Recommended)
1. Go to https://supabase.com
2. Click **New Project**
3. Fill in details, wait for setup (2 minutes)
4. Go to **Project Settings** → **Database**
5. Find **Connection string** → **URI**
6. Copy the **Session mode** connection (port 6543)
7. Replace `[YOUR-PASSWORD]` with your actual password

#### Option B: Your Platform's Database
- **Vercel:** Storage → Create Database → Postgres
- **Railway:** + New → Database → PostgreSQL  
- **Render:** New → PostgreSQL

### Step 2: Set Environment Variable

In your platform's dashboard (Vercel/Railway/Render):

1. Go to **Settings** → **Environment Variables**
2. Add:
   - **Name:** `DATABASE_URL`
   - **Value:** Your PostgreSQL connection string
   - **Example:** `postgresql://postgres:password@host:5432/dbname`

### Step 3: Redeploy

1. Save the environment variable
2. Trigger a new deployment (or push a commit)
3. Check logs - should see: "Using persistent database: django.db.backends.postgresql"

### Step 4: Verify

1. Create test data (invoice, customer, etc.)
2. Make another deployment
3. **Data should still be there!**

## What I Added

✅ **Automatic warnings** - App will warn you if using SQLite in production
✅ **Startup checks** - Logs will show database type on startup
✅ **Documentation** - See `docs/DATABASE_PERSISTENCE.md` for full guide

## After Fixing

Your data will:
- ✅ Persist across deployments
- ✅ Survive server restarts
- ✅ Not be lost on git pushes
- ✅ Be backed up by your database provider

## Need Help?

1. Check `docs/DATABASE_PERSISTENCE.md` for detailed instructions
2. Run `python scripts/check_database.py` to verify your setup
3. Check your platform's logs for database connection messages

## Cost

- **Supabase:** Free tier (500MB) - perfect for most apps
- **Other providers:** Usually $5-20/month

**This is NOT optional** - you will continue losing data until you switch to PostgreSQL.
