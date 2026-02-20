# Deploying to Vercel

This project is set up to run on **Vercel** as a serverless Django app. You get HTTPS, global CDN, and Git-based deploys. A few constraints apply (database, media, cold starts).

---

## What’s included in the repo

- **`api/wsgi.py`** — Vercel serverless entry; exposes the Django WSGI app as `app`.
- **`vercel.json`** — **routes** (matching the [official Django example](https://github.com/vercel/examples/tree/main/python/django)): `/static/` and `/media/` to static files, everything else to `api/wsgi.py`. No explicit `builds` so Vercel auto-detects the Python function.
- **`.vercelignore`** — Excludes `venv`, `.env`, `db.sqlite3`, `media/` from uploads.
- **Settings** — When the `VERCEL` env var is set, `ALLOWED_HOSTS` includes `.vercel.app` so the deployment URL works without extra config (you can still override with `ALLOWED_HOSTS`).

---

## Requirements

1. **PostgreSQL** — Vercel’s runtime is serverless and ephemeral. **SQLite is not suitable** (no persistent disk). Use one of:
   - [Supabase](https://supabase.com) — **recommended.** Create a project, then **Project Settings → Database → Connection string → URI**. Use the **Session pooler** (port **6543**) for serverless. Copy the URI and set **`DATABASE_URL`** or **`SUPABASE_URL`** in Vercel. The app enables SSL automatically for Supabase.
   - [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres), [Neon](https://neon.tech), or any hosted Postgres — set **`DATABASE_URL`** to a `postgresql://...` URL (the app accepts both `postgres://` and `postgresql://`).

2. **Environment variables** — Set these in the Vercel project (Settings → Environment Variables):

   | Variable | Required | Example / notes |
   |----------|----------|------------------|
   | `DJANGO_SECRET_KEY` | Yes | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
   | `DJANGO_DEBUG` | Yes | `0` in production |
   | `ALLOWED_HOSTS` | Optional on Vercel | If not set, app allows `*.vercel.app` when `VERCEL` is set. Set for custom domain, e.g. `yourapp.com,www.yourapp.com` |
   | `CSRF_TRUSTED_ORIGINS` | Yes for forms/login | Your app URL(s) with `https://`, e.g. `https://your-project.vercel.app` or `https://yourapp.com` |
   | `DATABASE_URL` | Yes | `postgresql://user:pass@host:5432/dbname` from your Postgres provider |

   **Vercel Blob (fieldops-blob):** If you added a Vercel Blob store (e.g. named `fieldops-blob`), Vercel sets `BLOB_READ_WRITE_TOKEN` automatically. The app uses it to store uploads (job photos, receipts, estimate images, etc.) in Blob instead of the ephemeral filesystem. No extra env var needed.

   Optional (same as other deploys): `QUICKBOOKS_*`, `MAPBOX_ACCESS_TOKEN`, `GOOGLE_MAPS_API_KEY`, etc.

3. **Build command** — So migrations and static files run on deploy, set in Vercel (Settings → General → Build & Development Settings):

   **Build Command:**
   ```bash
   pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
   ```

   Leave **Output Directory** empty. **Install Command** can be left default (Vercel will run `pip install -r requirements.txt` if you don’t override it; the build command above also installs deps).

4. **First deploy** — Ensure `DATABASE_URL` (and other required env vars) are set **before** the first deploy so the build can run `migrate` successfully.

---

## Connect Supabase to Vercel (step-by-step)

Supabase is **not** connected via a Vercel integration. You add the Supabase database connection string as an environment variable in Vercel.

### 1. Get the connection string from Supabase

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project.
2. Go to **Project Settings** (gear icon) → **Database**.
3. Scroll to **Connection string**.
4. Choose **URI**.
5. Select **Session mode** (connection pooler, port **6543**) — required for serverless.
6. Copy the URI. It looks like:
   ```text
   postgresql://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```
7. Replace **`[YOUR-PASSWORD]`** with your actual database password (the one you set when creating the project).  
   If the password contains `@`, `#`, `%`, or `/`, [URL-encode](https://www.urlencoder.org/) it.

### 2. Add it in Vercel

1. Open [Vercel Dashboard](https://vercel.com/dashboard) → your project.
2. Go to **Settings** → **Environment Variables**.
3. Add a new variable:
   - **Name:** `DATABASE_URL`
   - **Value:** the full URI you copied (with the real password).
   - **Environment:** check **Production** (and **Preview** if you want preview deploys to use the same DB).
4. Save.

### 3. Redeploy

- Go to **Deployments** → open the **⋯** menu on the latest deployment → **Redeploy** (or push a new commit).  
- The build will run `migrate` using `DATABASE_URL`; the app at runtime will use the same variable to connect to Supabase.

If the deploy or the app still doesn’t use Supabase, confirm the variable name is exactly `DATABASE_URL` (or `SUPABASE_URL`), that the password in the URI is correct, and that you redeployed after adding the variable.

---

## 404 on every page / Function not in the Functions tab

If the deployment builds but you get **404: NOT_FOUND**, or you **don’t see `api/wsgi` under Deployments → Functions**, Vercel is not deploying the Python serverless function. Fix in this order:

1. **Output Directory (most common cause)** — In Vercel → **Settings → General → Build & Development Settings**:
   - Find **Output Directory**.
   - Turn **Override** on and **leave the field completely empty** (delete any value like `staticfiles` or `build`).
   - Save. If this was set, only that folder was being deployed, so the `api/` function was never built.
2. **Framework Preset** — In the same section, set **Framework Preset** to **Other**. If it’s e.g. Next.js, the `api/` Python function is not built.
3. **Build Command** — You can leave it empty (the repo’s `vercel.json` sets `buildCommand` to `sh vercel-build.sh`). If you prefer to set it in the dashboard, use: `pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput`. Do not set an Output Directory.
4. **Redeploy** — **Deployments** → **⋯** on latest → **Redeploy**. Then open that deployment → **Functions** and confirm **api/wsgi** (or **api/wsgi.py**) appears.
5. If the function still doesn’t appear, check **Build** logs for errors and ensure **Root Directory** is blank (project root).

---

## Deploy steps

1. Push the repo to GitHub (if you haven’t already).
2. In [Vercel](https://vercel.com), **Add New Project** → Import your GitHub repo.
3. **Framework Preset:** leave as “Other” (or “None”).
4. **Root Directory:** leave default (repository root).
5. **Build Command:** set as above (migrate + collectstatic). Ensure Framework Preset is **Other** so the Django API function is deployed.
6. **Environment Variables:** add at least `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL`.
7. Deploy. When it finishes, open **https://&lt;your-project&gt;.vercel.app**.
8. Create a superuser (one-off): in Vercel dashboard → your project → **Settings** → **Functions** you can run a one-off command, or use **Vercel CLI** and run a local command that uses the same `DATABASE_URL` to run `python manage.py createsuperuser` against the production DB.

   **Option: create superuser via CLI with production DB**

   - Install [Vercel CLI](https://vercel.com/docs/cli) and link the project.
   - Pull envs: `vercel env pull .env.production`
   - Run: `python manage.py createsuperuser` (after `source .env.production` or loading those vars). That will create the user in the Vercel Postgres (or whatever DB you set in `DATABASE_URL`).

---

## Limitations and behavior

- **Cold starts** — The first request after idle can be slower (a few seconds) while the serverless function starts.
- **Execution time** — Hobby: 10s, Pro: 60s per request. Long-running tasks (e.g. big reports) may need to be offloaded to a background worker elsewhere.
- **Media uploads** — The serverless filesystem is read-only at runtime. **Add the Vercel Blob store** (e.g. `fieldops-blob`) to your project; Vercel will set `BLOB_READ_WRITE_TOKEN`. The app is configured to use Vercel Blob for all file uploads when that token is present, so job photos, receipts, estimate images, and logos will persist.
- **Bundle size** — Heavy dependencies (e.g. `opencv`, `numpy`, `pytesseract`) can push the function over Vercel’s limit. If the build or deploy fails with size errors, consider moving heavy work to an external service or trimming dependencies for the Vercel build.
- **Static files** — `vercel.json` routes `/static/*` to the `staticfiles` directory created by `collectstatic`. WhiteNoise is still in the app as a fallback.

---

## Custom domain

In the Vercel project: **Settings → Domains** → add your domain and follow DNS instructions. Then set:

- `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
- `CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`

---

## Summary checklist

- [ ] PostgreSQL created; `DATABASE_URL` set in Vercel
- [ ] `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `CSRF_TRUSTED_ORIGINS` set
- [ ] Build command includes `migrate` and `collectstatic`
- [ ] First deploy successful; open `https://<project>.vercel.app`
- [ ] Superuser created (CLI or one-off) so you can use `/admin/`
- [ ] (Optional) Custom domain and env vars updated
- [ ] **Supabase:** `DATABASE_URL` set in Vercel (Settings → Environment Variables) to the Supabase **Session mode** URI (port 6543), with `[YOUR-PASSWORD]` replaced. Then redeploy. See **Connect Supabase to Vercel** above if the DB isn’t connecting.
- [ ] (Recommended) Vercel Blob store (e.g. **fieldops-blob**) added to the project so uploads persist; `BLOB_READ_WRITE_TOKEN` is set automatically
