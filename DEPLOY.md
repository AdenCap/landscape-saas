# Deployment

## Digital Ocean App Platform (Supabase database)

The app reads the database URL from **`PG_URL`** first, then **`POSTGRES_URL`**. Use **`PG_URL`** if you have trouble—it’s a neutral name App Platform doesn’t validate.

**Critical:** The variable must be set on the **web service component** (the one that runs gunicorn) with scope **Run Time**. If it’s only set at “Build” or on a different component, the running app never sees it . The app now refuses to start on App Platform without a database URL (clear error in logs); if it starts, it is using Postgres and data will persist.

### Step-by-step: make data persist

1. **Get your Supabase connection URI**  
   Supabase → Project Settings → Database → Connection string → **URI**.  
   Example: `postgresql://postgres.xxxxx:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres`  
   Replace `YOUR_PASSWORD` with your database password.

2. **In Digital Ocean:** Your app → **Settings** → in the left sidebar click your **web service** (the component that runs the app, not “Static Site” or “Worker”).

3. **Environment Variables** for that component → **Edit** or **Add Variable**:
   - **Key:** `PG_URL` (or `POSTGRES_URL`)
   - **Value:** paste the full Supabase URI (no quotes)
   - **Scope:** **Run Time** (required). Do not use “Build” only.

4. **Save** and trigger a **full redeploy** (Deploy → Deploy latest or push a commit).

5. **Verify:** Set **`DB_CHECK_SECRET`** (e.g. `mysecret123`) in the same place, redeploy, then open:  
   `https://your-app.ondigitalocean.app/api/db-check/?key=mysecret123`  
   You should see “Database: PostgreSQL” and “Connection: OK”. If you see “Database: SQLite” and “PG_URL: not set”, the app still isn’t getting the variable—confirm it’s on the **web service** and scope is **Run Time**.

### Why does my data disappear after redeploy?

If user data (settings, records, etc.) is lost on every redeploy, the app is almost certainly using **SQLite** instead of Supabase. On App Platform the container filesystem is **ephemeral**: each new deploy gets a fresh filesystem, so any SQLite file (`db.sqlite3`) is wiped. Only an **external** database (Supabase) persists.

**Fix:** Ensure `POSTGRES_URL` is set for **runtime** (not just build):

1. In App Platform go to your app → **Settings** → **App-Level Environment Variables** (or the **web service** component’s env vars).
2. Add **POSTGRES_URL** with your full Supabase URI. Set its **scope** to **Run Time** (or “Run and Build”); it must be available when the app runs.
3. Redeploy. Check **Runtime Logs** when the app starts: look for `[DATABASE] Using PostgreSQL at ...` (good) or `[DATABASE] Using SQLite` (bad—fix env scope).
4. **Verify in the browser:** Set an env var `DB_CHECK_SECRET` (e.g. a random string like `abc123secret`). After deploy, open: `https://your-app.ondigitalocean.app/api/db-check/?key=abc123secret` (use your real secret). The page shows either "PostgreSQL at db.xxx.supabase.co" or "SQLite" and a warning.
5. In Supabase Table Editor, confirm that data appears after you use the app.

### Build and run commands

Use these in your App Platform component (Settings → Build & Run):

| Field | Value |
|-------|--------|
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| **Run Command** | `python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |

**Important:** Do **not** run `migrate` in the build command. The build phase often cannot reach Supabase (or does not have `DATABASE_URL`). Migrations run at **runtime** in the run command instead.

### Port

Set **HTTP Port** to `8080` (or leave default if your run command uses `$PORT`).

### Allowed hosts and CSRF (production)

When `DJANGO_DEBUG` is `0` or `False`, the app uses production security. **ALLOWED_HOSTS** is now set automatically when `PORT` is set (App Platform sets this): `.ondigitalocean.app` and `.render.com` are allowed so your app URL works without extra config. If you use a **custom domain**, set **ALLOWED_HOSTS** in env to your domain, e.g. `yourapp.com,www.yourapp.com`, and set **CSRF_TRUSTED_ORIGINS** to `https://yourapp.com,https://www.yourapp.com` so forms and login work.
