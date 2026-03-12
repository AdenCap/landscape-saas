# Stripe Dashboard Setup – Step-by-Step

This guide walks you through everything to do in the Stripe Dashboard and how to connect it to your FieldLgx platform.

---

## Prerequisites

- A Stripe account: [dashboard.stripe.com](https://dashboard.stripe.com) (use **Test mode** while developing).
- Your app running with a public URL for webhooks (e.g. ngrok for local: `https://xxxx.ngrok.io`).

---

## Part 1: Get your API keys

1. Go to **Stripe Dashboard** → [dashboard.stripe.com](https://dashboard.stripe.com).
2. Turn **Test mode** ON (toggle in the top right) while developing.
3. Go to **Developers** → **API keys**.
4. Copy and save:
   - **Publishable key** (starts with `pk_test_` or `pk_live_`) → you’ll set this as `STRIPE_PUBLISHABLE_KEY`.
   - **Secret key** (click “Reveal”, starts with `sk_test_` or `sk_live_`) → you’ll set this as `STRIPE_SECRET_KEY`.

Never commit these to git; put them in `.env` or your host’s environment variables.

---

## Part 2: Create the platform subscription product (businesses pay you)

This is the recurring plan each business pays to use FieldLgx.

1. In the Dashboard go to **Product catalog** → **Products**.
2. Click **+ Add product**.
3. Fill in:
   - **Name:** e.g. `FieldLgx – Monthly` (or “Annual” if you add a yearly option).
   - **Description:** optional, e.g. “Access to FieldLgx for your business.”
   - **Pricing:**
     - Choose **Standard pricing**.
     - **Price:** e.g. `29.00` USD (or whatever you want).
     - **Billing period:** Monthly (or One time / Yearly if you prefer).
4. Click **Save product**.
5. On the product page, under **Pricing**, you’ll see the price you just created. Click the **Price ID** (e.g. `price_1ABC...`) to copy it.
6. Save this as **`STRIPE_SUBSCRIPTION_PRICE_ID`** in your environment.

You can add more prices later (e.g. yearly) and change which price ID you use in code or config.

---

## Part 3: Set up the webhook (so your app gets subscription and payment events)

Your app receives events at one endpoint; Stripe signs them so you can verify they’re real.

1. Go to **Developers** → **Webhooks**.
2. Click **Add endpoint**.
3. **Endpoint URL:**  
   - Production: `https://fieldlgx.com/webhooks/stripe/`  
   - Local dev (e.g. ngrok): `https://your-ngrok-subdomain.ngrok.io/webhooks/stripe/`  
   Trailing slash must match what Django uses.
4. **Events to send:** click **Select events** and add:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `checkout.session.completed`
   - `account.updated`
5. Click **Add endpoint**.
6. On the new endpoint’s page, click **Reveal** under **Signing secret** and copy it (starts with `whsec_`).
7. Save this as **`STRIPE_WEBHOOK_SECRET`** in your environment.

Use the same endpoint for both subscription events and Connect events (invoice payments and `account.updated`).

---

## Part 4: Enable Stripe Connect (so businesses can accept invoice payments)

Connect lets each business get paid by their clients; your platform can take an optional fee.

1. Go to **Connect** → **Settings** (or **Get started** if you haven’t used Connect).
2. Complete any one-time Connect onboarding Stripe shows.
3. Under **Platform settings** (or **Integration**):
   - **Platform type:** Standard or Express.  
     This app uses **Express**: businesses go through Stripe’s hosted onboarding; you don’t handle their bank details.
4. Under **Branding** (optional): set your platform name and icon so Connect onboarding shows “Powered by [Your Platform]”.
5. No extra Dashboard “connection” step is required: as soon as Connect is enabled and you have the API keys above, your app can create Connect accounts and onboarding links.

Optional platform fee (you take a % of each invoice payment):

- In your app this is controlled by **`STRIPE_CONNECT_APPLICATION_FEE_PERCENT`** (e.g. `2.5` for 2.5%). Set it in your environment; you don’t have to turn on a special “fee” switch in the Dashboard.

---

## Part 5: Connect your platform (environment variables)

Set these where your app runs (e.g. `.env` in project root or your host’s env config):

```bash
# Required for subscriptions and Connect
STRIPE_SECRET_KEY=sk_test_xxxx          # from Part 1
STRIPE_PUBLISHABLE_KEY=pk_test_xxxx    # from Part 1
STRIPE_WEBHOOK_SECRET=whsec_xxxx      # from Part 3

# Required for “Subscribe” to work
STRIPE_SUBSCRIPTION_PRICE_ID=price_xxxx   # from Part 2

# Optional: platform fee on invoice payments (e.g. 2.5 for 2.5%)
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=0
```

Restart your Django app after changing env vars.

---

## Part 6: Quick checklist

| Step | Where | What you get |
|------|--------|----------------|
| 1 | Developers → API keys | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` |
| 2 | Product catalog → Add product + price | `STRIPE_SUBSCRIPTION_PRICE_ID` |
| 3 | Developers → Webhooks → Add endpoint | `STRIPE_WEBHOOK_SECRET` + URL `.../webhooks/stripe/` |
| 4 | Connect → Settings | Connect enabled (Express); optional branding |
| 5 | Your server / .env | All variables set and app restarted |

---

## Testing the connection

1. **Subscription (business pays you)**  
   - Log in as a business owner, go to **Settings** → **Subscription** (or `/subscription/`).  
   - Click “Subscribe now”. You should be sent to Stripe Checkout.  
   - Use test card `4242 4242 4242 4242`. After payment, you should be redirected back and have access; the webhook will set the business’s subscription status.

2. **Connect (business accepts payments)**  
   - As owner, go to **Settings** → “Connect Stripe to accept card payments”.  
   - Complete Stripe’s onboarding (use test data).  
   - After “charges enabled”, open an invoice pay link (from a sent invoice).  
   - You should see “Pay with card”; paying there should send money to the connected account and mark the invoice paid (via `checkout.session.completed` webhook).

3. **Webhook**  
   - In Stripe Dashboard → Developers → Webhooks → your endpoint, check **Recent deliveries**.  
   - Failed deliveries usually mean wrong URL, wrong secret, or app error; fix the error and Stripe can retry.

---

## Going live

1. Turn **Test mode** OFF in the Dashboard.
2. Create a **live** Product/Price for the subscription and set **`STRIPE_SUBSCRIPTION_PRICE_ID`** to the live Price ID.
3. Create a **new webhook** endpoint with your **production** URL and subscribe the same events; set **`STRIPE_WEBHOOK_SECRET`** to the new endpoint’s signing secret.
4. Replace keys with **live** keys: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` (live keys start with `sk_live_` and `pk_live_`).
5. Redeploy and test with a real card (small amount) before relying on it.

That’s everything you need to do on the Stripe Dashboard and to connect your platform.
