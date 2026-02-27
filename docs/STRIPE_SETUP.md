# Stripe Integration Setup Guide

This guide covers setting up Stripe Billing (subscriptions) and Stripe Connect (invoice payments) for the Field Ops platform.

## Overview

The platform uses two Stripe integrations:

1. **Stripe Billing**: Companies pay a monthly subscription to access the SaaS
2. **Stripe Connect**: Companies can accept credit card payments on invoices from their clients (funds go to the company's bank account)

## Environment Variables

Add these to your `.env` file or environment:

```bash
# Required: Stripe API keys
STRIPE_SECRET_KEY=sk_live_...  # or sk_test_... for testing
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret from Stripe Dashboard

# Required: Subscription pricing
STRIPE_SUBSCRIPTION_PRICE_ID=price_...  # Price ID for monthly subscription

# Optional: Platform fee on invoice payments (percentage, e.g., 2.5 for 2.5%)
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=0  # Set to 0 for no fee (current default)

# Optional: Separate webhook secret for Connect events (if using separate endpoint)
# STRIPE_CONNECT_WEBHOOK_SECRET=whsec_...
```

## Stripe Dashboard Setup

### 1. Create Stripe Account

1. Sign up at https://stripe.com
2. Get your API keys from https://dashboard.stripe.com/apikeys
3. Copy the **Secret key** (starts with `sk_`) to `STRIPE_SECRET_KEY`

### 2. Create Subscription Price

1. Go to Products → Create product
2. Set up a recurring monthly subscription
3. Copy the **Price ID** (starts with `price_`) to `STRIPE_SUBSCRIPTION_PRICE_ID`

### 3. Set Up Webhooks

1. Go to Developers → Webhooks
2. Click "Add endpoint"
3. Set endpoint URL to: `https://yourdomain.com/webhooks/stripe/`
4. Select events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `account.updated` (for Stripe Connect)
5. Copy the **Signing secret** (starts with `whsec_`) to `STRIPE_WEBHOOK_SECRET`

### 4. Enable Stripe Connect

1. Go to Settings → Connect
2. Enable Connect (Express accounts)
3. Configure your Connect settings (branding, terms, etc.)

## Local Testing with Stripe CLI

### Install Stripe CLI

```bash
# macOS
brew install stripe/stripe-cli/stripe

# Linux/Windows: see https://stripe.com/docs/stripe-cli
```

### Forward Webhooks Locally

```bash
# Login to Stripe
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/webhooks/stripe/

# This will output a webhook signing secret (whsec_...)
# Use this for STRIPE_WEBHOOK_SECRET in local development
```

### Test Events

```bash
# Test subscription checkout completion
stripe trigger checkout.session.completed

# Test subscription creation
stripe trigger customer.subscription.created

# Test subscription update
stripe trigger customer.subscription.updated

# Test Connect account update
stripe trigger account.updated
```

## How It Works

### Subscription Flow (Stripe Billing)

1. **Company subscribes**:
   - Owner goes to `/subscription/`
   - Clicks "Subscribe now"
   - Redirected to Stripe Checkout
   - After payment, webhook sets `subscription_status = "active"`

2. **Subscription management**:
   - Owner can access Billing Portal from `/subscription/`
   - Can update payment method, cancel, etc.

3. **Access control**:
   - `SubscriptionRequiredMiddleware` checks for active subscription
   - Platform admins bypass subscription requirement

### Invoice Payment Flow (Stripe Connect)

1. **Company connects Stripe**:
   - Owner goes to Settings → "Connect Stripe to accept card payments"
   - Completes Stripe Express onboarding
   - Webhook sets `stripe_connect_charges_enabled = True`

2. **Client pays invoice**:
   - Owner sends invoice to client
   - Client clicks "Pay with card" link
   - Checkout session created in **connected account context**
   - Funds go directly to company's Stripe account (not platform)
   - Webhook marks invoice as "paid" and stores payment IDs

3. **Payment tracking**:
   - Invoice stores: `stripe_checkout_session_id`, `stripe_payment_intent_id`, `stripe_charge_id`
   - All payments are tracked for reconciliation

## Database Schema

### Business Model (Stripe fields)

- `stripe_customer_id`: Stripe Customer ID for subscriptions
- `stripe_subscription_id`: Active subscription ID
- `subscription_status`: "active", "trialing", "canceled", etc.
- `subscription_current_period_end`: When current period ends
- `stripe_connect_account_id`: Connected account ID
- `stripe_connect_charges_enabled`: Whether account can accept charges
- `stripe_connect_application_fee_percent`: Platform fee % (optional)

### Invoice Model (Stripe fields)

- `stripe_checkout_session_id`: Checkout session for payment
- `stripe_payment_intent_id`: Payment intent ID
- `stripe_charge_id`: Charge ID

### StripeWebhookEvent Model

- `event_id`: Stripe event ID (for idempotency)
- `event_type`: Event type
- `processed`: Whether event was processed
- `raw_data`: Full event JSON (for debugging)

## Security Features

1. **Webhook signature verification**: All webhooks verified using signing secret
2. **Idempotency**: Events tracked to prevent duplicate processing
3. **Idempotency keys**: All Stripe API calls use idempotency keys
4. **Server-side only**: Stripe secret keys never exposed to client
5. **Authorization**: Users can only act on their own Stripe resources

## Troubleshooting

### Webhooks not working

1. Check webhook secret is correct
2. Verify endpoint URL in Stripe Dashboard
3. Check webhook event logs in Stripe Dashboard
4. Review `StripeWebhookEvent` table for errors

### Subscription not activating

1. Check webhook events in Stripe Dashboard
2. Verify `STRIPE_SUBSCRIPTION_PRICE_ID` is correct
3. Check `StripeWebhookEvent` table for processing errors
4. Ensure webhook handler is receiving events

### Invoice payments not working

1. Verify company has completed Stripe Connect onboarding
2. Check `stripe_connect_charges_enabled` is `True`
3. Verify connected account is in good standing
4. Check webhook events for `checkout.session.completed`

## Production Checklist

- [ ] Use live Stripe keys (not test keys)
- [ ] Set `STRIPE_WEBHOOK_SECRET` from production webhook endpoint
- [ ] Configure webhook endpoint URL in Stripe Dashboard
- [ ] Test subscription flow end-to-end
- [ ] Test invoice payment flow end-to-end
- [ ] Monitor webhook event processing
- [ ] Set up alerts for failed webhooks
- [ ] Review Stripe Dashboard regularly for issues

## Support

For Stripe-specific issues:
- Stripe Documentation: https://stripe.com/docs
- Stripe Support: https://support.stripe.com

For platform issues:
- Check webhook event logs in `StripeWebhookEvent` table
- Review Django logs for errors
- Check Stripe Dashboard for event details
