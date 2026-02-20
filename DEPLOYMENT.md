# Deploying Field Ops to the Internet

This guide covers publishing your Django app so anyone can sign up and use it.

- **Vercel (serverless):** see **[docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md)** for deploy steps, required env vars, PostgreSQL, and limitations (media, cold starts).
- **Secure deploy on your own server (VPS):** see **[docs/SECURE_DEPLOYMENT.md](docs/SECURE_DEPLOYMENT.md)** for server hardening, HTTPS (Let's Encrypt), Nginx, Gunicorn, PostgreSQL, and a full security checklist.

---

## 1. What’s already in place

- **Public signup** at `/accounts/signup/`: new users create a business and an owner account, then are logged in.
- **Production-ready settings**: `SECRET_KEY`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` can be set via environment variables.

---

## 2. Hosting options (pick one)

| Platform | Best for | Free tier | Notes |
|----------|----------|-----------|--------|
| **Railway** | Easiest deploy from GitHub | Yes (limits) | Add-ons for DB, env vars in dashboard |
| **Render** | Simple, good docs | Yes (spins down) | Web Service + optional PostgreSQL |
| **Fly.io** | Global regions, more control | Yes (limits) | Run Django + optional Postgres |
| **PythonAnywhere** | Very simple, no Docker | Yes | Good for small traffic, SQLite or MySQL |
| **DigitalOcean App Platform** | Predictable pricing | No | Managed app + DB |
| **Your VPS** (Linode, Hetzner, etc.) | Full control | No | You manage server, Nginx, Gunicorn, SSL |

**Recommendation for “anyone can sign up”:** Railway or Render — connect your repo, set env vars, and deploy. For more traffic or a real database later, add PostgreSQL and switch `DATABASES` in settings.

---

## 3. Production checklist

Before going live:

1. **Set environment variables** (never commit these):
   - `DJANGO_SECRET_KEY` — e.g. `python -c "import secrets; print(secrets.token_urlsafe(50))"`
   - `DJANGO_DEBUG=0`
   - `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com` (or the host your platform gives you, e.g. `yourapp.railway.app`)
   - `CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com` (same as above with `https://`)

2. **Database**  
   - For small/medium use, SQLite is fine; ensure the app has a **persistent volume** so `db.sqlite3` isn’t lost on redeploy (Railway/Render/Fly all support this).  
   - For **PostgreSQL** (recommended for Vercel/production): use **Supabase** (set `DATABASE_URL` or `SUPABASE_URL` to the connection URI from Project Settings → Database; use Session pooler port 6543 for serverless), or any hosted Postgres with `DATABASE_URL`.

3. **Static files**  
   - In production, serve static files with WhiteNoise or your platform’s static asset step.  
   - Add to `requirements.txt`: `whitenoise`  
   - In `settings.py`: add `whitenoise` to `MIDDLEWARE` (after `SecurityMiddleware`), and set `STATIC_ROOT = BASE_DIR / "staticfiles"`.  
   - Run `python manage.py collectstatic` as part of your deploy (or in the build step).

4. **HTTPS**  
   - Use the platform’s HTTPS (Railway/Render/Fly provide it). If you use a custom domain, add it in the dashboard and set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` accordingly.

5. **Optional**  
   - **Email**: For password reset and notifications, set an SMTP backend (e.g. SendGrid, Mailgun) and `DEFAULT_FROM_EMAIL`.  
   - **QuickBooks**: Set `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`, and `QUICKBOOKS_REDIRECT_URI` to your production callback URL.  
   - **Mapbox**: Set `MAPBOX_ACCESS_TOKEN` if you use the property estimator.

---

## 4. Example: deploy on Railway

1. Push your code to GitHub.
2. Go to [railway.app](https://railway.app), sign in, **New Project** → **Deploy from GitHub** → select this repo.
3. Add a **Postgres** service if you want (optional; otherwise use SQLite + persistent volume).
4. In your web service → **Variables**, add:
   - `DJANGO_SECRET_KEY` = (generate as above)
   - `DJANGO_DEBUG` = `0`
   - `ALLOWED_HOSTS` = `yourapp.railway.app` (or your custom domain)
   - `CSRF_TRUSTED_ORIGINS` = `https://yourapp.railway.app`
5. In **Settings** → **Deploy**, set **Start Command** to something like:
   - `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
6. Add `gunicorn` to `requirements.txt` if not already there.
7. Deploy. Your app will be at `https://yourapp.railway.app`; signup is at `https://yourapp.railway.app/accounts/signup/`.

---

## 5. Example: deploy on Render

1. Push your code to GitHub.
2. Go to [render.com](https://render.com), **New** → **Web Service**, connect the repo.
3. **Build command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput` (if using WhiteNoise).  
4. **Start command**: `gunicorn config.wsgi:application`.  
5. In **Environment**, add `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`.  
6. Deploy. Use the Render URL (e.g. `https://yourapp.onrender.com`) in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

---

## 6. After deploy

- Open `https://your-app-url/accounts/signup/` and create an account to confirm signup works.
- Use `https://your-app-url/admin/` only with a superuser (create one locally and sync DB, or run `python manage.py createsuperuser` in a one-off shell on the host).

Once this is done, anyone can sign up and use the app at your public URL.
