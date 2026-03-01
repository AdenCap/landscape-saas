# Application Fees and Free Subscriptions Guide

This guide explains how to configure application fees for invoice payments and how to grant free subscriptions to businesses.

## Application Fees

### How Application Fees Work

When a customer pays an invoice with a credit card:
1. Payment goes directly to the business owner's Stripe account (Direct Charge)
2. Platform can optionally take an application fee (percentage of the payment)
3. Application fee is deducted from the payment before it reaches the business

### Configuration Options

#### Global Default Fee

Set in your `.env` file:
```bash
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=2.5  # 2.5% fee for all businesses
```

Or set to `0` for no fee:
```bash
STRIPE_CONNECT_APPLICATION_FEE_PERCENT=0  # No fee by default
```

#### Per-Business Fee Override

You can set different fees for different businesses:

1. **Via Django Admin:**
   - Go to Admin → Businesses → Select a business
   - Find "Stripe – subscription & Connect" section
   - Set `stripe_connect_application_fee_percent`:
     - Leave blank = use global default
     - Set to `0` = no fee for this business
     - Set to `2.5` = 2.5% fee for this business
     - Set to `5` = 5% fee for this business

2. **Via Code:**
   ```python
   business = Business.objects.get(id=123)
   business.stripe_connect_application_fee_percent = 0  # No fee
   business.save()
   ```

### Fee Calculation Examples

- Invoice amount: $100
- Global fee: 2.5%
- Business fee override: None (uses global)
- **Result:** Business receives $97.50, platform gets $2.50

- Invoice amount: $100
- Global fee: 2.5%
- Business fee override: 0 (no fee)
- **Result:** Business receives $100.00, platform gets $0.00

- Invoice amount: $100
- Global fee: 2.5%
- Business fee override: 5.0 (higher fee)
- **Result:** Business receives $95.00, platform gets $5.00

### When to Use Application Fees

**Consider charging fees if:**
- You provide value beyond just payment processing
- You want to monetize the platform
- You offer additional services (support, features, etc.)

**Consider waiving fees for:**
- Early adopters or beta testers
- Strategic partners
- High-volume customers (as an incentive)
- Businesses that bring significant value

## Free Subscriptions

### Granting Free Access

You can give businesses free access to the platform (no subscription required):

1. **Via Django Admin:**
   - Go to Admin → Businesses → Select a business
   - Find "Stripe – subscription & Connect" section
   - Check the `subscription_is_free` checkbox
   - Save

2. **Via Code:**
   ```python
   business = Business.objects.get(id=123)
   business.subscription_is_free = True
   business.save()
   ```

### How Free Subscriptions Work

- Business with `subscription_is_free = True` has full platform access
- No Stripe subscription required
- No payment needed
- Works exactly like an active subscription

### When to Grant Free Subscriptions

**Good candidates:**
- Beta testers providing feedback
- Strategic partners
- Early adopters who helped build the product
- Non-profit organizations (if applicable)
- Businesses you're acquiring or merging with

### Combining Free Subscription + No Application Fee

You can give a business both:
- Free subscription (`subscription_is_free = True`)
- No application fee (`stripe_connect_application_fee_percent = 0`)

This gives them:
- Free platform access
- Free payment processing (no fees on invoice payments)

## Recommendations

### Starting Out

1. **No fees initially:**
   - Set `STRIPE_CONNECT_APPLICATION_FEE_PERCENT=0`
   - Focus on growth and user acquisition
   - Build value before monetizing

2. **Free subscriptions for early users:**
   - Grant free access to first 10-20 businesses
   - Build loyalty and testimonials
   - Get valuable feedback

### As You Grow

1. **Introduce fees gradually:**
   - Start with 1-2% for new businesses
   - Grandfather existing businesses at 0%
   - Use fees to fund platform improvements

2. **Tiered pricing:**
   - Free tier: No subscription, but charge fees on payments
   - Paid tier: Monthly subscription, lower/no fees on payments
   - Enterprise: Custom pricing

### Best Practices

1. **Be transparent:**
   - Clearly communicate fees to businesses
   - Show fees in invoices/emails
   - Provide fee breakdown in dashboard

2. **Monitor and adjust:**
   - Track fee revenue
   - Monitor business satisfaction
   - Adjust fees based on market conditions

3. **Document exceptions:**
   - Keep notes on why businesses have free access
   - Document fee overrides and reasons
   - Review periodically

## Admin Actions

### Bulk Grant Free Subscription

You can create a Django admin action to grant free subscriptions to multiple businesses:

```python
@admin.action(description='Grant free subscription to selected businesses')
def grant_free_subscription(modeladmin, request, queryset):
    queryset.update(subscription_is_free=True)
    modeladmin.message_user(request, f"Granted free subscription to {queryset.count()} businesses.")

BusinessAdmin.actions = [grant_free_subscription]
```

### Bulk Set Application Fee

```python
@admin.action(description='Set application fee to 0% for selected businesses')
def remove_application_fee(modeladmin, request, queryset):
    queryset.update(stripe_connect_application_fee_percent=0)
    modeladmin.message_user(request, f"Removed application fee for {queryset.count()} businesses.")

BusinessAdmin.actions.append(remove_application_fee)
```

## FAQ

**Q: Can I charge different fees to different businesses?**
A: Yes! Set `stripe_connect_application_fee_percent` per business in admin.

**Q: Can I give a business free subscription AND no application fee?**
A: Yes! Set both `subscription_is_free = True` and `stripe_connect_application_fee_percent = 0`.

**Q: Will businesses see the application fee?**
A: The fee is deducted automatically. The business receives the net amount. You may want to show this in your dashboard.

**Q: Can I change fees later?**
A: Yes, you can update fees at any time. Changes apply to future payments only.

**Q: What's a reasonable application fee?**
A: Typical range is 0-5%. Stripe charges ~2.9% + $0.30, so consider that when setting your fee.
