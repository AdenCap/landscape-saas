# Quick Start: Launch Checklist

## 🚀 Absolute Minimum to Go Live (30 minutes)

### Step 1: Stripe Setup (15 min)
1. Create account at https://stripe.com
2. Get API keys: https://dashboard.stripe.com/apikeys
3. Create subscription product:
   - Products → Create product
   - Recurring monthly
   - Set your price
   - Copy Price ID
4. Set up webhook:
   - Developers → Webhooks → Add endpoint
   - URL: `https://fieldlgx.com/webhooks/stripe/`
   - Select events: `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `account.updated`
   - Copy signing secret

### Step 2: Deploy to Hosting (10 min)
**Railway (Recommended):**
1. Push code to GitHub
2. Go to railway.app → New Project → Deploy from GitHub
3. Add environment variables (see below)
4. Deploy

**Render:**
1. Push code to GitHub
2. Go to render.com → New Web Service
3. Connect repo
4. Add environment variables
5. Deploy

### Step 3: Environment Variables (5 min)
Add these in your hosting platform's dashboard:

```bash
# Required
DJANGO_SECRET_KEY=<generate-with-python-command-below>
DJANGO_DEBUG=0
ALLOWED_HOSTS=fieldlgx.com,www.fieldlgx.com
CSRF_TRUSTED_ORIGINS=https://fieldlgx.com,https://www.fieldlgx.com

# Stripe (REQUIRED for payments)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUBSCRIPTION_PRICE_ID=price_...
```

**Generate Secret Key:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 4: Test (5 min)
1. Visit your site
2. Sign up as a new user
3. Go to Subscription page
4. Click "Subscribe now"
5. Complete test payment
6. Verify you can access the app

---

## ✅ That's It!

Once these 4 steps are done, your software is live and accepting payments.

---

## 📋 Full Production Checklist

See **[docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md)** for:
- Email configuration
- Database setup
- Legal requirements
- Monitoring
- Backups
- And more...

---

## 🆘 Common Issues

**"Subscription not working"**
- Check `STRIPE_WEBHOOK_SECRET` is set correctly
- Verify webhook endpoint URL in Stripe Dashboard
- Check webhook events are being received

**"Can't access app after signup"**
- Check subscription webhook processed
- Verify `subscription_status` is "active" in database
- Check middleware isn't blocking access

**"Invoice payments not working"**
- Verify company connected Stripe (Settings → Connect Stripe)
- Check `stripe_connect_charges_enabled` is True
- Verify webhook is processing `checkout.session.completed`

---

## 💰 Pricing Recommendation

**Suggested pricing:**
- **Starter:** $49/month (small businesses, < 10 employees)
- **Professional:** $99/month (medium businesses, < 50 employees)
- **Enterprise:** $199/month (large businesses, unlimited)

Start with one price, add tiers later if needed.

---

## 📞 Next Steps After Launch

1. **Week 1:** Monitor for errors, respond to support requests
2. **Week 2:** Gather feedback, fix bugs
3. **Month 1:** Review analytics, plan improvements
4. **Ongoing:** Add features, optimize, scale

---

**You're ready to launch!** 🎉
