# Digital Ocean + Supabase — Complete Setup

Use this as your checklist. Configure everything on the **web service** component (the one that runs your app).

---

## 1. Build & Run (Settings → your web service → Build & Run)

| Field | Value |
|-------|--------|
| **Build Command** | `pip install --no-cache-dir -r requirements.txt && python manage.py collectstatic --noinput` |
| **Run Command** | `python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| **HTTP Port** | `8080` |

---

## 2. Environment Variables (Settings → web service → Environment Variables)

Add these on the **web service** component. Use **Encrypted** for secrets. Set **Scope** to **Run Time** for all of them (so the running app sees them).

### Required (app won’t start without these)

| Key | Value | Scope | Notes |
|-----|--------|--------|--------|
| **PG_URL** | Your Supabase connection URI | **Run Time** | See “Get PG_URL” below. |
| **DJANGO_SECRET_KEY** | A long random string (e.g. 50 chars) | Run Time | For sessions/security. Generate one and keep it secret. |

### Optional but recommended

| Key | Value | Scope | Notes |
|-----|--------|--------|--------|
| **DJANGO_DEBUG** | `0` | Run Time | Use `0` in production. |
| **DB_CHECK_SECRET** | Any secret string (e.g. `mysecret123`) | Run Time | Lets you open `/api/db-check/?key=YOUR_SECRET` to verify Postgres. |

### Optional (if you use these features)

| Key | Value | Scope |
|-----|--------|--------|
| **STRIPE_SECRET_KEY** | Your Stripe secret key | Run Time |
| **STRIPE_PUBLISHABLE_KEY** | Your Stripe publishable key | Run Time |
| **STRIPE_WEBHOOK_SECRET** | Your Stripe webhook secret | Run Time |
| **STRIPE_SUBSCRIPTION_PRICE_ID** | Your subscription price ID | Run Time |
| **QUICKBOOKS_CLIENT_ID** | QuickBooks client ID | Run Time |
| **QUICKBOOKS_CLIENT_SECRET** | QuickBooks client secret | Run Time |
| **ALLOWED_HOSTS** | Only if using a custom domain, e.g. `yourapp.com,www.yourapp.com` | Run Time |
| **CSRF_TRUSTED_ORIGINS** | Only if custom domain, e.g. `https://yourapp.com,https://www.yourapp.com` | Run Time |

---

## 3. Get PG_URL (Supabase)

1. Open [Supabase](https://supabase.com) → your project.
2. **Project Settings** (gear) → **Database**.
3. Under **Connection string**, choose **URI**.
4. Copy the URI. It looks like:
   ```text
   postgresql://postgres.[PROJECT_REF]:[YOUR-PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with your actual database password (the one you set for the project).
6. Paste that full string as the value of **PG_URL** in Digital Ocean (no quotes).

---

## 4. Verify after deploy

1. Save all env vars and redeploy.
2. In **Runtime Logs**, you should see: `[DATABASE] Using PostgreSQL at db.xxxx.supabase.co`
3. If you set **DB_CHECK_SECRET**, open in a browser:
   ```text
   https://YOUR-APP-URL.ondigitalocean.app/api/db-check/?key=YOUR_SECRET
   ```
   You should see “Database: PostgreSQL” and “Connection: OK”.

---

## 5. Quick checklist

- [ ] Build Command and Run Command set as above  
- [ ] HTTP Port = 8080  
- [ ] **PG_URL** = full Supabase URI, **Run Time**  
- [ ] **DJANGO_SECRET_KEY** = long random string, **Run Time**  
- [ ] (Optional) **DJANGO_DEBUG** = 0  
- [ ] (Optional) **DB_CHECK_SECRET** for `/api/db-check/`  
- [ ] Saved and redeployed  

If the app starts and you see `[DATABASE] Using PostgreSQL` in the logs, data will persist across redeploys.

---

## Build failing?

1. **Copy the exact error** from the build log (Digital Ocean → your app → Deployments → click the failed build → build logs). The last 20–30 lines usually show the real failure (e.g. `pip install` error, `ModuleNotFoundError`, or `collectstatic` error).

2. **Use this build command** (saves disk and can avoid timeouts):
   ```bash
   pip install --no-cache-dir -r requirements.txt && python manage.py collectstatic --noinput
   ```

3. **If `pip install` fails** on a specific package (e.g. `opencv-python-headless`, `Pillow`):
   - Check that the **Install Command** (if set) is just `pip install --no-cache-dir -r requirements.txt` and that the **Build Command** is `python manage.py collectstatic --noinput`, or keep a single Build Command as above.
   - Digital Ocean uses Python 3.13 by default; if the error is about an old Python, in the dashboard set **Environment** or **Python version** to 3.11 or 3.12 if available.

4. **If `collectstatic` fails**: the log will show a Django traceback. Paste that into your next message so we can fix the exact line.

---

## "No route to host" or database connection failure

This usually means the app cannot reach Supabase’s database host. Try these in order:

### 1. Restore a paused Supabase project (very common)

Free-tier Supabase projects **pause after inactivity**. When paused, the DB is off and you get "No route to host".

- Open [Supabase Dashboard](https://supabase.com/dashboard) → your project.
- If you see **"Project is paused"** or **"Restore project"**, click **Restore** and wait until the project is running again.
- Redeploy your app on Digital Ocean after the project is active.

### 2. Use the connection pooler (Session mode) instead of direct

Sometimes the **pooler** host is reachable when the direct host is not.

- In Supabase: **Project Settings** → **Database** → **Connection string**.
- Choose **URI**, then select **Session mode** (connection pooler).
- Copy the URI. It will look like:
  ```text
  postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-XX.pooler.supabase.com:6543/postgres
  ```
  (Different host: `pooler.supabase.com` and port **6543**.)
- Replace the password and set this as **PG_URL** in Digital Ocean (Run Time). Redeploy.

### 3. Double-check PG_URL

- No quotes or spaces; one continuous string.
- Password in the URI must be **URL-encoded** if it contains `@`, `#`, `%`, `/`, or `?` (e.g. use `%40` for `@`).
- In Supabase, you can reset the database password (Project Settings → Database) and use the new password in the URI.
