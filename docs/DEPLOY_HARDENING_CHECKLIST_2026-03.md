# Deploy Hardening Checklist (Solo + Pro Subscriptions)

Use this checklist after each production deploy.

## 1) Environment Variables

Required minimum for single-web deployment:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG=0`
- `ALLOWED_HOSTS` (include DO app domain + custom domain)
- `CSRF_TRUSTED_ORIGINS` (https origins only)
- `DATABASE_URL` (Supabase transaction pooler URI, sslmode=require)

Billing/subscription vars:

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_SUBSCRIPTION_PRICE_ID` (Pro All-Access)
- `STRIPE_SUBSCRIPTION_PRICE_ID_SOLO` (Solo Starter)
- `STRIPE_TRIAL_DAYS_SOLO` (recommended 7)
- `STRIPE_TRIAL_DAYS_PRO` (recommended 14)
- `PLATFORM_SOLO_PRICE=29.99`
- `PLATFORM_PRO_PRICE=99.99`
- `PLATFORM_CREW_SOFT_CAP=12`

## 2) Web Component Commands

Build:
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

Run:
```bash
python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8080
```

## 3) Stripe Webhook

Endpoint:

`https://<your-domain>/webhooks/stripe/`

Enable at least:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

## 4) Post-Deploy Smoke Tests

### Public marketing funnel

- `/` landing renders
- `/features/`, `/automation/`, `/pricing/` render
- Sign in link visible for existing users
- Signup CTA paths are clear and working

### Subscription flow

- `/subscription/status/` shows Solo + Pro cards
- Solo button starts checkout with Solo price
- Pro button starts checkout with Pro price
- Trial days apply by plan (if configured)
- Return from checkout updates account plan tier

### Access behavior

- Solo users: calendar + clients access only
- Pro users: full feature access
- Complimentary access toggle still works in platform admin

## 5) Health and Error Checks

- Deployment logs: no DB `No route to host` errors
- Migrations complete successfully
- App responds on port 8080
- `manage.py check` clean in logs

## 6) Fast Troubleshooting

### If DB fails with `No route to host`

- Confirm `DATABASE_URL` is **transaction pooler** host (`*.pooler.supabase.com`)
- Confirm `sslmode=require`
- Remove conflicting old DB env vars (`PG_URL`/`POSTGRES_URL`) if needed

### If checkout fails

- Verify both Stripe price IDs are correct and active
- Verify webhook secret matches endpoint in Stripe dashboard

### If plan tier not updating

- Check webhook delivery logs in Stripe
- Confirm `customer.subscription.updated` events are arriving

---

For cost control, run single web component only. Add Celery worker/beat later when background automation must run continuously.
