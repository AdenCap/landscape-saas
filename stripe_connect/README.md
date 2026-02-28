# Stripe Connect V2 Integration

A comprehensive Stripe Connect V2 integration for Django that allows businesses to onboard to Stripe, create products, run a storefront, and manage subscriptions.

## Features

- **V2 Connected Account Onboarding**: Create and onboard connected accounts using Stripe Connect V2 API
- **Product Management**: Create and manage products on connected accounts
- **Storefront**: Public-facing storefront for customers to browse and purchase products
- **Direct Charges with Application Fees**: Process payments with platform fees
- **Subscription Management**: Create and manage subscriptions for connected accounts
- **Webhook Handling**: Process V2 account events and subscription events

## Setup

### 1. Install Dependencies

Make sure the Stripe SDK is installed:

```bash
pip install stripe>=8.0
```

### 2. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...  # Your Stripe secret key
STRIPE_PUBLISHABLE_KEY=pk_test_...  # Your Stripe publishable key
STRIPE_WEBHOOK_SECRET=whsec_...  # Webhook signing secret (see Webhook Setup below)
STRIPE_SUBSCRIPTION_PRICE_ID=price_...  # Price ID for platform subscriptions (optional)
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=2.5  # Platform fee percentage (optional, default 0)
```

**IMPORTANT**: 
- Replace `sk_test_...` with your actual Stripe secret key
- Replace `pk_test_...` with your actual Stripe publishable key
- The webhook secret will be provided when you set up webhooks (see below)

### 3. Run Migrations

```bash
python manage.py migrate stripe_connect
```

### 4. Configure Webhooks

#### In Stripe Dashboard:

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → **Developers** → **Webhooks**
2. Click **+ Add destination**
3. Configure:
   - **Events from**: Select "Connected accounts"
   - **Payload style**: Select "Thin"
   - **Events**: Add the following V2 events:
     - `v2.core.account[requirements].updated`
     - `v2.core.account[configuration.merchant].capability_status_updated`
     - `v2.core.account[configuration.customer].capability_status_updated`
   - **URL**: `https://yourdomain.com/webhooks/stripe-connect/`
4. Copy the **Signing secret** to `STRIPE_WEBHOOK_SECRET` in your `.env`

#### For Subscriptions (Regular Events):

Add these events to your webhook endpoint (can be same endpoint or different):

- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `payment_method.attached`
- `payment_method.detached`
- `customer.updated`
- `customer.tax_id.created`
- `customer.tax_id.updated`
- `customer.tax_id.deleted`
- `billing_portal.configuration.created`
- `billing_portal.configuration.updated`
- `billing_portal.session.created`

**Note**: Subscription events use regular (not thin) events.

### 5. Local Testing with Stripe CLI

For local development, use Stripe CLI to forward webhooks:

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli

# Listen for thin events (V2 accounts)
stripe listen --thin-events 'v2.core.account[requirements].updated,v2.core.account[configuration.merchant].capability_status_updated,v2.core.account[configuration.customer].capability_status_updated' --forward-thin-to http://localhost:8000/webhooks/stripe-connect/

# Or listen for all events (subscriptions + V2 accounts)
stripe listen --forward-to http://localhost:8000/webhooks/stripe-connect/
```

The CLI will provide a webhook signing secret. Use this for `STRIPE_WEBHOOK_SECRET` during local development.

## Usage

### Onboarding a Business

1. Business owner navigates to `/stripe-connect/dashboard/`
2. Clicks "Onboard to Collect Payments"
3. Completes Stripe onboarding flow
4. Returns to dashboard to see account status

### Creating Products

1. Navigate to `/stripe-connect/products/`
2. Click "Create Product"
3. Fill in product details (name, description, price)
4. Product is created on the connected account

### Storefront

- Public URL: `/stripe-connect/storefront/{account_id}/`
- Customers can browse products and make purchases
- **Note**: In production, use a more secure identifier than `account_id` in the URL

### Subscriptions

1. Business owner navigates to dashboard
2. Clicks "Create Subscription"
3. Completes checkout
4. Can manage subscription via "Billing Portal"

## Code Structure

### Models

- `ConnectedAccount`: Maps Business to Stripe account ID
- `ConnectedProduct`: Products created on connected accounts
- `ConnectedSubscription`: Subscriptions for connected accounts
- `ConnectWebhookEvent`: Webhook event tracking for idempotency

### Views

- `connect_onboard`: Create account and start onboarding
- `connect_dashboard`: View account status
- `product_list` / `product_create`: Product management
- `storefront`: Public storefront
- `create_checkout_session`: Create checkout for purchases
- `subscription_create` / `billing_portal`: Subscription management

### Webhooks

- `stripe_connect_webhook`: Main webhook endpoint
- Handles both thin events (V2) and regular events (subscriptions)
- `handle_thin_event`: Process V2 account events
- `handle_subscription_event`: Process subscription lifecycle events

## Important Notes

### V2 Accounts

- V2 accounts use a single account ID (`acct_xxx`) for both merchant and customer operations
- Use `customer_account` parameter (not `customer`) for subscriptions
- Account ID format: `acct_xxx` (not `acct_connect_xxx`)

### Stripe-Account Header

When making requests on behalf of a connected account, use the `stripeAccount` parameter:

```python
# Python example
stripe_client.products.list(
    limit=20,
    stripe_account=account_id,  # Connected account ID
)
```

### Application Fees

Application fees are set in the checkout session:

```python
payment_intent_data={
    'application_fee_amount': 123,  # Amount in cents
}
```

Calculate fees based on your platform fee percentage.

### Error Handling

All views check for Stripe configuration and show helpful error messages if:
- Stripe SDK is not installed
- `STRIPE_SECRET_KEY` is not configured
- Webhook secret is missing

## Security Considerations

1. **Webhook Signing**: Always verify webhook signatures
2. **Account Verification**: Verify account ownership before operations
3. **Storefront URLs**: In production, use secure identifiers instead of account IDs
4. **API Keys**: Never commit API keys to version control
5. **HTTPS**: Always use HTTPS in production

## Testing

1. Use Stripe test mode keys (`sk_test_...`, `pk_test_...`)
2. Use Stripe CLI for local webhook testing
3. Test with Stripe test cards: https://stripe.com/docs/testing

## Troubleshooting

### "Stripe SDK not installed"
- Run: `pip install stripe>=8.0`

### "STRIPE_SECRET_KEY not configured"
- Add `STRIPE_SECRET_KEY` to your `.env` file
- Restart your Django server

### Webhook signature verification fails
- Ensure `STRIPE_WEBHOOK_SECRET` matches the secret from Stripe Dashboard
- For local testing, use the secret from Stripe CLI

### Account not found errors
- Ensure the business has completed onboarding
- Check that `ConnectedAccount` record exists in database

## API Version

This integration uses Stripe API version `2026-02-25.clover` (automatically used by the SDK).

## Documentation

- [Stripe Connect V2 Docs](https://docs.stripe.com/connect/accounts)
- [Stripe Python SDK](https://github.com/stripe/stripe-python)
- [Stripe Webhooks Guide](https://docs.stripe.com/webhooks)
