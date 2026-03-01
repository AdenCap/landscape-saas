# Digital Ocean + Supabase — Complete Setup

Use this as your checklist. Configure everything on the **web service** component (the one that runs your app).

---

## 1. Build & Run (Settings → your web service → Build & Run)

| Field | Value |
|-------|--------|
| **Build Command** | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
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
