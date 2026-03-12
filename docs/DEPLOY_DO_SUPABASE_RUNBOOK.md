# FieldLgx — DigitalOcean + Supabase Production Runbook

## 1) Supabase
1. Create project.
2. Copy Postgres connection string.
3. Prefer pooler for app traffic.
4. Verify SSL required.

## 2) DigitalOcean App Platform env vars (Web + Worker)
Required:
- DJANGO_SECRET_KEY
- DJANGO_DEBUG=0
- ALLOWED_HOSTS=fieldlgx.com,www.fieldlgx.com,<app>.ondigitalocean.app
- CSRF_TRUSTED_ORIGINS=https://fieldlgx.com,https://www.fieldlgx.com,https://<app>.ondigitalocean.app
- PG_URL=postgresql://...
- STRIPE_SECRET_KEY
- STRIPE_PUBLISHABLE_KEY
- STRIPE_WEBHOOK_SECRET
- STRIPE_SUBSCRIPTION_PRICE_ID

Recommended:
- REDIS_URL=redis://...
- CACHE_URL=redis://...
- CELERY_BROKER_URL=redis://...
- CELERY_RESULT_BACKEND=redis://...
- SENTRY_DSN
- DB_CHECK_ENABLED=0

## 3) Deploy using app spec
- `.do/app.yaml` now includes:
  - web service (migrate + gunicorn)
  - celery worker service

## 4) DNS
- Point `fieldlgx.com` and `www` to App Platform app.
- Enable managed TLS in DO.

## 5) Stripe
- Webhook endpoint: `https://fieldlgx.com/webhooks/stripe/`
- Verify events delivered and no 5xx loops.

## 6) Smoke tests
1. Login
2. Create/update record
3. Redeploy
4. Confirm record still exists (persistence check)
5. Stripe test checkout + webhook update path
6. Check worker logs for Celery heartbeat

## 7) Backups
- Enable Supabase backups/PITR.
- Schedule monthly restore drill to staging.
