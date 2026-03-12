# DigitalOcean: Next Steps After Adding Environment Variables

## ✅ What You've Done
- Added all environment variables to DigitalOcean App Platform
- App should be ready to deploy

## 🚀 Next Steps

### 1. Verify Your Variables (2 minutes)

**Double-check these are all set:**
- [ ] `DJANGO_SECRET_KEY` - Should be 50+ characters
- [ ] `DJANGO_DEBUG=0` - Must be `0` (not `False` or empty)
- [ ] `ALLOWED_HOSTS` - Your domain or DigitalOcean app URL
- [ ] `CSRF_TRUSTED_ORIGINS` - HTTPS URLs matching ALLOWED_HOSTS
- [ ] `STRIPE_SECRET_KEY` - Starts with `sk_live_...`
- [ ] `STRIPE_WEBHOOK_SECRET` - Starts with `whsec_...`
- [ ] `STRIPE_SUBSCRIPTION_PRICE_ID` - Starts with `price_...`

### 2. Check Build & Run Commands (1 minute)

**In DigitalOcean App Settings → General:**

**Build Command:**
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

**Run Command:**
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8080
```

**OR** if you have a `Procfile` or `run.sh`, DigitalOcean should detect it automatically.

### 3. Deploy Your App (5 minutes)

**Option A: Auto-Deploy from GitHub**
- If you connected GitHub, push to your main branch
- DigitalOcean will automatically deploy

**Option B: Manual Deploy**
- Go to your App → "Deployments" tab
- Click "Create Deployment" or "Redeploy"

**Watch the build:**
- Go to "Activity" tab
- Watch for any errors
- Should see "Build succeeded" and "Deploy succeeded"

### 4. Get Your App URL (1 minute)

**After deployment:**
- DigitalOcean gives you a URL like: `https://your-app-name-xxxxx.ondigitalocean.app`
- Or use your custom domain if configured

**Note this URL** - you'll need it for:
- Testing
- Stripe webhook configuration
- Updating ALLOWED_HOSTS if needed

### 5. Configure Stripe Webhook (5 minutes)

**Now that your app is live:**

1. **Get your webhook URL:**
   - Your app URL: `https://your-app-name.ondigitalocean.app`
   - Webhook endpoint: `https://your-app-name.ondigitalocean.app/webhooks/stripe/`

2. **In Stripe Dashboard:**
   - Go to https://dashboard.stripe.com/webhooks
   - Click "Add endpoint"
   - Endpoint URL: `https://your-app-name.ondigitalocean.app/webhooks/stripe/`
   - Select events:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `account.updated`
   - Click "Add endpoint"
   - Copy the "Signing secret" (starts with `whsec_...`)

3. **Add to DigitalOcean:**
   - Go back to App → Settings → Environment Variables
   - Update `STRIPE_WEBHOOK_SECRET` with the new signing secret
   - App will auto-redeploy

### 6. Test Everything (10 minutes)

**Test these critical flows:**

1. **Visit Your App:**
   - Go to your app URL
   - Should see the landing page

2. **Test Signup:**
   - Click "Get started"
   - Create a test account
   - Should create business and log you in

3. **Test Subscription:**
   - Go to `/subscription/` (or Settings → Subscription)
   - Click "Subscribe now"
   - Complete test payment in Stripe
   - Should redirect back and give you access

4. **Test App Access:**
   - After subscribing, you should see the dashboard
   - Can create jobs, clients, etc.

5. **Test Stripe Connect:**
   - Go to Settings → "Connect Stripe to accept card payments"
   - Complete onboarding
   - Should enable invoice payments

### 7. Set Up Custom Domain (Optional, 10 minutes)

**If you have a domain:**

1. **In DigitalOcean:**
   - App → Settings → Domains
   - Click "Add Domain"
   - Enter your domain (e.g., `fieldlgx.com`)

2. **Update DNS:**
   - DigitalOcean will show you DNS records to add
   - Add them to your domain registrar (Namecheap, GoDaddy, etc.)
   - Wait for DNS to propagate (5-60 minutes)

3. **Update Environment Variables:**
   - After domain is active, update:
     - `ALLOWED_HOSTS=fieldlgx.com,www.fieldlgx.com`
     - `CSRF_TRUSTED_ORIGINS=https://fieldlgx.com,https://www.fieldlgx.com`
   - Redeploy

---

## 🔍 Troubleshooting

### "App won't start"
- Check "Activity" tab for error logs
- Verify run command is correct
- Check all required env vars are set

### "502 Bad Gateway" or "Application Error"
- Check build logs in "Activity" tab
- Verify `DJANGO_DEBUG=0` (not `False`)
- Check `ALLOWED_HOSTS` includes your app URL

### "Subscription not working"
- Verify `STRIPE_WEBHOOK_SECRET` is set correctly
- Check webhook URL in Stripe Dashboard matches your app URL
- Check "Activity" logs for webhook errors
- Verify webhook events are being received in Stripe Dashboard

### "Can't access after signup"
- Check subscription webhook processed successfully
- Verify `subscription_status` is "active" in database
- Check middleware isn't blocking (should allow platform admins)

---

## ✅ Success Checklist

After deployment, verify:

- [ ] App loads at your URL
- [ ] Landing page displays correctly
- [ ] Can sign up new account
- [ ] Can subscribe (test payment)
- [ ] Can access app after subscription
- [ ] Can create jobs, clients, invoices
- [ ] Stripe Connect onboarding works
- [ ] Invoice payments work (if Connect enabled)

---

## 📊 Monitor Your App

**DigitalOcean provides:**
- Activity logs (deployments, errors)
- Metrics (CPU, memory, requests)
- Alerts (can set up notifications)

**Check regularly:**
- Activity tab for errors
- Stripe Dashboard for payment issues
- App metrics for performance

---

## 🎉 You're Live!

Once all tests pass, your software is live and accepting customers!

**Next steps:**
1. Monitor for first few days
2. Respond to any customer issues quickly
3. Gather feedback
4. Plan feature improvements

---

**Need Help?**
- DigitalOcean Support: Available in dashboard
- Check Activity logs for errors
- Review [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for more details
