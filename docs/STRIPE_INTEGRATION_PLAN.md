# Stripe Integration Plan: End-to-End Payments

This document describes the two payment flows and how they are implemented.

---

## 1. Two Payment Operations

### A. Platform subscription (Business → You)

- **What:** Each business (company) pays a recurring subscription to you for access to FieldLgx.
- **Flow:** Business signs up → after signup or first login they are prompted to subscribe (or have a trial). They pay via Stripe Checkout (subscription). Recurring charges go to **your** Stripe account.
- **Access control:** Only businesses with an active (or trialing) subscription can use the app. Others are redirected to the subscription page.

### B. Invoice payments (Customer → Business)

- **What:** Each business’s clients pay that business for invoices (e.g. “Pay invoice #123”).
- **Flow:** Business connects their own Stripe account (Stripe Connect). When a customer clicks “Pay with card” on the invoice pay page, a Stripe Checkout Session is created with the **connected account** so funds go to that business. Your platform can optionally take an application fee.
- **Result:** Each business gets paid by their clients; you can take a small platform fee if desired.

---

## 2. Implementation Summary

| Component | Purpose |
|-----------|--------|
| **Business model fields** | `stripe_customer_id`, `stripe_subscription_id`, `subscription_status`, `subscription_current_period_end` (platform subscription); `stripe_connect_account_id`, `stripe_connect_charges_enabled` (Connect) |
| **Subscription app** | Checkout for plan, Customer Portal link, webhook for `customer.subscription.*` and `invoice.paid` (platform) |
| **Billing + Connect** | Connect onboarding (Express or Standard), “Pay with card” on invoice pay page (Checkout with `stripe_account=connected_account_id`), webhook for `checkout.session.completed` (invoice payment) |
| **Access control** | Middleware or decorator: require `subscription_status in ('active', 'trialing')` for dashboard/billing/jobs etc.; exclude subscription and login/signup |
| **Settings / Billing UI** | “Subscription” section (plan, next billing, manage link); “Accept payments” section (Connect onboarding or “Dashboard” if already connected) |

---

## 3. Environment Variables

- `STRIPE_SECRET_KEY` – Your Stripe secret key (platform).
- `STRIPE_PUBLISHABLE_KEY` – Publishable key for Stripe.js/Checkout (platform).
- `STRIPE_WEBHOOK_SECRET` – Webhook signing secret (one endpoint can handle both subscription and Connect events).
- `STRIPE_SUBSCRIPTION_PRICE_ID` – (Optional) Default price ID for the platform plan (e.g. monthly). Can also be set in code or admin.
- `STRIPE_CONNECT_APPLICATION_FEE_PERCENT` – (Optional) Platform fee on invoice payments (e.g. 2 for 2%).

---

## 4. Stripe Dashboard Setup

1. **Products & prices** – Create a product “FieldLgx” with a recurring price (e.g. monthly/yearly). Copy the Price ID(s) into settings or env.
2. **Connect** – Enable Stripe Connect (Express or Standard). Note: Express is simpler for businesses (they get a Stripe-hosted onboarding).
3. **Webhooks** – Add endpoint `https://fieldlgx.com/webhooks/stripe/`, events: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `checkout.session.completed`, `account.updated` (for Connect). Use the same endpoint for both subscription and Connect events.

---

## 5. Files Touched / Added

- `businesses/models.py` – New fields for subscription + Connect.
- `subscription/` – New app: views (subscribe, portal), webhook, urls.
- `billing/views.py` – Connect onboarding, invoice pay with Stripe (Checkout).
- `billing/urls.py` – Routes for Connect and pay.
- `config/settings.py` – Stripe keys, subscription price ID, `subscription` app, middleware if used.
- `config/urls.py` – Include subscription + webhook URL.
- `accounts/decorators.py` or new middleware – Require active subscription.
- Templates – Subscription page, Connect onboarding link, invoice pay page “Pay with card” button.

---

## 6. Security Notes

- Webhook: verify signature using `STRIPE_WEBHOOK_SECRET`; return 200 only after processing.
- Never expose secret key to the frontend; use Publishable Key for Stripe.js/Checkout client-side if needed.
- Connect: store only `stripe_connect_account_id`; do not store connected account secret keys.
