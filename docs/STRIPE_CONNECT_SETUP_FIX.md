# Fix: Stripe Connect Account Creation Error

## Error Message

```
Could not create Stripe account: Please review the responsibilities of managing losses for connected accounts at https://dashboard.stripe.com/settings/connect/platform-profile.
```

## What This Means

When creating Stripe Connect V2 accounts, Stripe requires you to configure how losses (chargebacks, disputes, refunds) are handled. This is a **one-time setup** in your Stripe Dashboard.

## How to Fix

### Step 1: Go to Stripe Dashboard

1. Log in to your Stripe Dashboard: https://dashboard.stripe.com
2. Make sure you're in the correct mode (Test or Live) - use Test mode first!

### Step 2: Navigate to Connect Settings

1. Click on **Settings** in the left sidebar
2. Click on **Connect** (under "Platform settings")
3. Click on **Platform profile** (or go directly to: https://dashboard.stripe.com/settings/connect/platform-profile)

### Step 3: Configure Loss Responsibility

You'll see a section about **"Loss responsibility"** or **"Managing losses for connected accounts"**.

You have two options:

#### Option A: Stripe Manages Losses (Recommended for most platforms)

- **Stripe is responsible** for losses (chargebacks, disputes, refunds)
- Connected accounts don't need to worry about disputes
- Stripe handles everything automatically
- **This is what our code expects** (we set `losses_collector: "stripe"`)

**To enable:**
1. Select "Stripe manages losses" or "Stripe is responsible"
2. Review and accept the terms
3. Save the settings

#### Option B: Connected Accounts Manage Losses

- Each connected account is responsible for their own losses
- More complex setup
- Requires additional configuration

**Note:** If you choose this option, you'll need to update the code to set `losses_collector: "connected_account"` instead of `"stripe"`.

### Step 4: Configure Fee Responsibility (if shown)

You may also see a setting for **"Fee responsibility"**:
- **Stripe collects fees** - Stripe automatically deducts fees (recommended)
- **Platform collects fees** - You handle fee collection manually

Our code sets `fees_collector: "stripe"`, so make sure Stripe collects fees is enabled.

### Step 5: Save and Test

1. Save all settings
2. Go back to your application
3. Try creating a connected account again
4. It should work now!

## Code Configuration

Our code already sets the correct values:

```python
defaults={
    "responsibilities": {
        "fees_collector": "stripe",      # Stripe collects fees
        "losses_collector": "stripe",    # Stripe manages losses
    },
}
```

This matches **Option A** above. Make sure your Stripe Dashboard settings match.

## Additional Requirements

While you're in the Connect settings, also verify:

1. **Connect is enabled** - Make sure Stripe Connect is activated for your account
2. **Webhook endpoint** - Your webhook endpoint is configured
3. **API keys** - You're using the correct API keys (test vs live)

## Testing

After configuring:

1. **Test mode first:**
   - Use test API keys (`sk_test_...`)
   - Create a test connected account
   - Verify it works

2. **Then go live:**
   - Switch to live API keys (`sk_live_...`)
   - Configure live Connect settings
   - Create real connected accounts

## Troubleshooting

### Still getting the error?

1. **Check you're in the right mode:**
   - Test mode settings ≠ Live mode settings
   - Configure both if needed

2. **Check API key:**
   - Make sure `STRIPE_SECRET_KEY` matches the mode you're testing in
   - Test keys start with `sk_test_`
   - Live keys start with `sk_live_`

3. **Wait a few minutes:**
   - Sometimes Stripe needs a moment to process settings changes
   - Try again after 2-3 minutes

4. **Check Stripe status:**
   - Visit https://status.stripe.com
   - Make sure there are no outages

### Need to change loss responsibility later?

If you want to switch from "Stripe manages losses" to "Connected accounts manage losses":

1. Update Dashboard settings
2. Update code to set `losses_collector: "connected_account"`
3. Note: This may require re-onboarding existing accounts

## Quick Checklist

- [ ] Logged into Stripe Dashboard
- [ ] Navigated to Connect → Platform profile
- [ ] Selected "Stripe manages losses"
- [ ] Selected "Stripe collects fees"
- [ ] Saved settings
- [ ] Using correct API keys (test vs live)
- [ ] Tried creating account again

## Support

If you're still having issues:
- Stripe Support: https://support.stripe.com
- Stripe Connect Docs: https://docs.stripe.com/connect
- Check your Stripe Dashboard for any additional requirements
