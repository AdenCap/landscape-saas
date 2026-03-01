# Stripe Connect V2 Integration

This module provides a complete Stripe Connect V2 integration for your Django application, allowing businesses to accept payments from their customers through your platform.

## Features

- **V2 Account Creation**: Create connected accounts using Stripe's V2 API
- **Onboarding Flow**: Complete onboarding using Stripe Account Links
- **Product Management**: Create and manage products on connected accounts
- **Storefront**: Public storefront for customers to purchase products
- **Direct Charge**: Process payments with application fees
- **Connected Account Subscriptions**: Allow connected accounts to subscribe to your platform
- **Billing Portal**: Manage subscriptions through Stripe's billing portal
- **Webhook Support**: Handle V2 thin events for account requirements and capability updates

## Setup

### 1. Environment Variables

Add the following to your `.env` file:

```bash
# Required: Your Stripe secret key (from https://dashboard.stripe.com/apikeys)
STRIPE_SECRET_KEY=sk_test_...  # or sk_live_... for production

# Optional: Application fee percentage (e.g., 2.5 for 2.5%)
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=0

# Optional: Subscription price ID for connected accounts
STRIPE_SUBSCRIPTION_PRICE_ID=price_...

# Required: Webhook signing secret (from Stripe Dashboard → Webhooks)
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. Database Migrations

Run migrations to create the necessary database tables:

```bash
python manage.py migrate stripe_connect
```

### 3. Webhook Configuration

In your Stripe Dashboard:

1. Go to **Developers** → **Webhooks**
2. Click **+ Add destination**
3. Select **Connected accounts** in "Events from"
4. Select **Show advanced options** → **Thin** in "Payload style"
5. Add your webhook URL: `https://yourdomain.com/webhooks/stripe/`
6. Select these events:
   - `v2.core.account[requirements].updated`
   - `v2.core.account[configuration.merchant].capability_status_updated`
   - `v2.core.account[configuration.customer].capability_status_updated`
   - `v2.core.account[.recipient].capability_status_updated`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `checkout.session.completed`
   - And any other events you need
7. Copy the **Signing secret** to `STRIPE_WEBHOOK_SECRET`

### 4. Local Testing with Stripe CLI

For local development, use the Stripe CLI to forward webhooks:

```bash
# Install Stripe CLI (if not installed)
# macOS: brew install stripe/stripe-cli/stripe
# Linux/Windows: https://stripe.com/docs/stripe-cli

# Login
stripe login

# Forward webhooks with thin events
stripe listen --thin-events 'v2.core.account[requirements].updated,v2.core.account[configuration.merchant].capability_status_updated,v2.core.account[configuration.customer].capability_status_updated,v2.core.account[.recipient].capability_status_updated,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,checkout.session.completed' --forward-thin-to http://localhost:8000/webhooks/stripe/
```

Use the webhook signing secret from the CLI output in your `.env` file.

## Usage

### Onboarding a Business

1. Business owner navigates to `/stripe-connect/onboarding/`
2. Clicks "Onboard to Collect Payments"
3. Completes Stripe's hosted onboarding flow
4. Returns to your application with account connected

### Creating Products

1. Business owner navigates to `/stripe-connect/products/`
2. Fills out product form (name, description, price)
3. Product is created on their connected Stripe account
4. Products appear in their storefront

### Storefront

Public storefront URL: `/stripe-connect/store/<account_id>/`

**Note**: In production, you should use a more user-friendly identifier (like a slug) instead of the account ID in the URL.

### Processing Payments

When a customer purchases a product:
1. Checkout session is created with Direct Charge
2. Application fee is calculated based on `STRIPE_CONNECT_APPLICATION_FEE_PERCENT`
3. Payment goes to connected account, fee goes to platform
4. Customer is redirected to success page

### Connected Account Subscriptions

Allow connected accounts to subscribe to your platform:
1. Business owner navigates to `/stripe-connect/subscription/`
2. Clicks "Start Subscription"
3. Completes checkout on Stripe
4. Subscription is tracked in database
5. Use billing portal to manage subscription

## Code Structure

### Models

- `ConnectedAccountProduct`: Stores products created on connected accounts
- `ConnectedAccountSubscription`: Tracks subscriptions for connected accounts

### Views

- `connect_onboarding`: Onboarding flow and status
- `create_account_link`: Creates Account Link for onboarding
- `product_list`: List and create products
- `storefront`: Public storefront for customers
- `create_checkout_session`: Creates checkout session for purchases
- `connect_subscription`: Subscription management for connected accounts
- `create_billing_portal_session`: Opens billing portal

### Webhook Handlers

Located in `subscription/handlers.py`:

- `_v2_account_requirements_updated`: Handles requirement changes
- `_v2_merchant_capability_updated`: Updates when card payments are enabled
- `_connect_subscription_created/updated/deleted`: Manages subscriptions
- And more...

## Important Notes

### V2 API Usage

- **Never use top-level `type` parameter** when creating accounts
- Use `customer_account` instead of `customer` for V2 account subscriptions
- Use `stripe_account` parameter (or `stripeAccount` header) for all API calls to connected accounts

### Application Fees

Application fees are calculated automatically based on:
1. Business-level `stripe_connect_application_fee_percent` (if set)
2. Global `STRIPE_CONNECT_APPLICATION_FEE_PERCENT` setting (fallback)

### Error Handling

All Stripe operations include:
- Helpful error messages if `STRIPE_SECRET_KEY` is not set
- Detailed logging for debugging
- User-friendly error messages in the UI

### Security

- Never expose `STRIPE_SECRET_KEY` to the frontend
- Always verify webhook signatures
- Use idempotency keys for critical operations
- Validate user permissions (only owners can manage their account)

## Testing

1. Use Stripe test mode keys (`sk_test_...`)
2. Create test connected accounts
3. Test the full flow: onboarding → products → checkout → webhooks
4. Verify application fees are calculated correctly
5. Test subscription flow for connected accounts

## Troubleshooting

### "STRIPE_SECRET_KEY is not set"

Add `STRIPE_SECRET_KEY` to your `.env` file with your Stripe secret key.

### Webhook events not received

1. Check webhook endpoint URL in Stripe Dashboard
2. Verify `STRIPE_WEBHOOK_SECRET` matches the signing secret
3. For local testing, use Stripe CLI to forward events
4. Check webhook event logs in Stripe Dashboard

### Account not ready to process payments

1. Check account status in Stripe Dashboard
2. Verify all required information is provided
3. Check `requirements_status` in the onboarding page
4. Complete any pending requirements

### Products not showing in storefront

1. Verify products are created on the correct connected account
2. Check that products are marked as `active`
3. Verify `stripe_account` parameter is used when listing products

## Additional Resources

- [Stripe Connect Documentation](https://stripe.com/docs/connect)
- [Stripe V2 Accounts API](https://docs.stripe.com/api/v2/core/accounts)
- [Stripe Webhooks Guide](https://docs.stripe.com/webhooks)
- [Thin Events Documentation](https://docs.stripe.com/webhooks?snapshot-or-thin=thin)
