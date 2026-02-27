# Production Readiness Checklist

This guide covers everything you need to make Field Ops publicly available and ready for customers to pay for subscriptions.

## 🚨 Critical: Must-Have Before Launch

### 1. Stripe Configuration (REQUIRED for payments)

**You MUST set these up or customers cannot subscribe:**

1. **Create Stripe Account**
   - Sign up at https://stripe.com
   - Complete business verification
   - Get your API keys from https://dashboard.stripe.com/apikeys

2. **Set Environment Variables:**
   ```bash
   STRIPE_SECRET_KEY=sk_live_...  # Use LIVE keys in production (not test)
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...  # From webhook endpoint
   STRIPE_SUBSCRIPTION_PRICE_ID=price_...  # Create a subscription product
   ```

3. **Create Subscription Product:**
   - Go to Products → Create product
   - Set up recurring monthly subscription
   - Set your price (e.g., $99/month)
   - Copy the Price ID to `STRIPE_SUBSCRIPTION_PRICE_ID`

4. **Set Up Webhooks:**
   - Go to Developers → Webhooks → Add endpoint
   - URL: `https://yourdomain.com/webhooks/stripe/`
   - Select events:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `account.updated` (for Stripe Connect)
   - Copy the signing secret to `STRIPE_WEBHOOK_SECRET`

5. **Enable Stripe Connect:**
   - Go to Settings → Connect
   - Enable Express accounts
   - Configure branding and terms

**Test:** Create a test subscription to verify everything works.

---

### 2. Production Deployment

**Choose a hosting platform:**

| Platform | Cost | Best For | Setup Time |
|----------|------|----------|------------|
| **Railway** | $5-20/mo | Easiest, good for startups | 10 min |
| **Render** | $7-25/mo | Simple, good docs | 15 min |
| **Fly.io** | $5-15/mo | Global, more control | 20 min |
| **DigitalOcean** | $12+/mo | Predictable pricing | 30 min |
| **Vercel** | Free tier | Serverless (see docs) | 15 min |

**Recommended: Railway or Render** for fastest setup.

**Required Environment Variables for Production:**
```bash
# Django Core
DJANGO_SECRET_KEY=<generate-strong-key>
DJANGO_DEBUG=0
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:port/dbname

# Stripe (see above)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_SUBSCRIPTION_PRICE_ID=price_...
```

**Generate Secret Key:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### 3. Database Setup

**Option A: SQLite (Simple, for small scale)**
- Works out of the box
- Ensure persistent storage (volume) so data isn't lost
- Good for < 1000 users

**Option B: PostgreSQL (Recommended for production)**
- Use Supabase (free tier available) or hosted Postgres
- Set `DATABASE_URL` environment variable
- Better performance and scalability

**Migration:**
```bash
python manage.py migrate
```

---

### 4. Domain & SSL

1. **Buy a domain** (e.g., from Namecheap, Google Domains)
2. **Point DNS** to your hosting platform
3. **Enable HTTPS** (most platforms do this automatically)
4. **Update environment variables:**
   - `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
   - `CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`

---

### 5. Email Configuration (REQUIRED for invoices/estimates)

**Companies need to send invoices and estimates to clients.**

**Option A: Gmail (per-business, configured in Settings)**
- Each company sets up their own Gmail in Settings
- Requires Gmail App Password
- Free but limited

**Option B: Transactional Email Service (Recommended)**
- **SendGrid** (free tier: 100 emails/day)
- **Mailgun** (free tier: 5,000 emails/month)
- **AWS SES** (very cheap, pay per email)

**Set in settings.py or environment:**
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'  # or your provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # for SendGrid
EMAIL_HOST_PASSWORD = 'your-api-key'
DEFAULT_FROM_EMAIL = 'Field Ops <noreply@yourdomain.com>'
```

**Note:** Companies can still use Gmail in Settings, but platform-level email is better for notifications.

---

### 6. Security Checklist

- [ ] `DJANGO_DEBUG=0` in production
- [ ] Strong `DJANGO_SECRET_KEY` (50+ characters)
- [ ] `ALLOWED_HOSTS` set correctly
- [ ] `CSRF_TRUSTED_ORIGINS` set for HTTPS
- [ ] HTTPS enabled (SSL certificate)
- [ ] Database credentials secure (env vars, not in code)
- [ ] Stripe keys are LIVE keys (not test keys)
- [ ] Webhook secret is set and verified
- [ ] Platform admin account secured (strong password, 2FA)

---

### 7. Legal & Compliance

**Before accepting payments, you should have:**

1. **Terms of Service**
   - What customers agree to when using the software
   - Subscription terms, cancellation policy
   - Liability limitations

2. **Privacy Policy**
   - How you handle customer data
   - GDPR compliance if serving EU customers
   - Data retention policies

3. **Refund Policy**
   - Clear policy on subscription refunds
   - Prorated refunds for cancellations?

4. **Business Registration**
   - Register your business (LLC, Corp, etc.)
   - Get EIN/Tax ID
   - Set up business bank account

5. **Tax Compliance**
   - Sales tax (if required in your state)
   - Income tax on subscription revenue
   - 1099 forms for contractors (if applicable)

**Templates:** Use services like LegalZoom, or consult a lawyer.

---

### 8. Testing Before Launch

**Test these critical flows:**

1. **Signup Flow:**
   - [ ] New user can sign up
   - [ ] Business is created
   - [ ] User is logged in automatically

2. **Subscription Flow:**
   - [ ] User can view subscription page
   - [ ] "Subscribe now" button works
   - [ ] Stripe Checkout opens
   - [ ] Payment succeeds
   - [ ] Webhook processes subscription
   - [ ] User gets access to app

3. **Stripe Connect Flow:**
   - [ ] Company can connect Stripe
   - [ ] Onboarding completes
   - [ ] Invoice payment checkout works
   - [ ] Funds go to company's account

4. **Core Features:**
   - [ ] Create job
   - [ ] Complete job
   - [ ] Create invoice
   - [ ] Send invoice
   - [ ] View dashboard
   - [ ] Filter jobs (past 7 days, 30 days, etc.)

5. **Admin Features:**
   - [ ] Platform admin can access `/platform/`
   - [ ] Can view analytics
   - [ ] Can enter company dashboards

---

### 9. Monitoring & Error Tracking

**Set up error tracking:**

1. **Sentry** (Recommended)
   - Free tier: 5,000 events/month
   - Tracks errors, performance issues
   - Get alerts when things break

2. **Logging:**
   - Set up application logs
   - Monitor webhook processing
   - Track subscription events

3. **Uptime Monitoring:**
   - Use UptimeRobot (free) or Pingdom
   - Get alerts if site goes down

---

### 10. Backup Strategy

**Critical: Back up your database regularly**

1. **Automated Backups:**
   - Most hosting platforms offer automated backups
   - Set up daily backups
   - Test restore process

2. **Manual Backups:**
   ```bash
   # PostgreSQL
   pg_dump database_name > backup.sql
   
   # SQLite
   cp db.sqlite3 backup-$(date +%Y%m%d).sqlite3
   ```

3. **Backup Storage:**
   - Store backups in S3, Google Cloud Storage, or similar
   - Keep at least 30 days of backups
   - Test restore process monthly

---

### 11. Performance Optimization

**Before launch, optimize:**

1. **Database Indexes:**
   - Already have indexes on key fields
   - Monitor slow queries

2. **Static Files:**
   - Use WhiteNoise or CDN
   - Run `python manage.py collectstatic`

3. **Caching:**
   - Consider Redis for caching (if high traffic)
   - Current setup uses in-memory cache (fine for start)

4. **Image Optimization:**
   - Compress uploaded images
   - Use appropriate image sizes

---

### 12. Documentation for Users

**Create user-facing docs:**

1. **Getting Started Guide**
   - How to sign up
   - How to subscribe
   - Basic features overview

2. **Feature Documentation**
   - How to create jobs
   - How to send invoices
   - How to connect Stripe
   - How to use calendar

3. **FAQ Page**
   - Common questions
   - Troubleshooting
   - Support contact

---

### 13. Support System

**Set up customer support:**

1. **Support Email:**
   - Create support@yourdomain.com
   - Set up email forwarding
   - Respond within 24 hours

2. **Help Center:**
   - Use Help Scout, Zendesk, or similar
   - Or simple email for now

3. **In-App Help:**
   - Add "Help" or "Support" link in navigation
   - Link to documentation

---

### 14. Marketing Landing Page

**Already implemented:**
- ✅ Landing page at `/`
- ✅ Feature showcase
- ✅ Signup CTA

**Consider adding:**
- Pricing page (if multiple tiers)
- Testimonials
- Demo video
- Case studies

---

### 15. Analytics

**Track usage and conversions:**

1. **Google Analytics:**
   - Track signups
   - Track subscription conversions
   - Monitor user behavior

2. **Stripe Dashboard:**
   - Monitor subscription revenue
   - Track churn
   - View customer metrics

3. **Platform Admin Dashboard:**
   - Already tracks users, revenue, businesses
   - Use `/platform/` for internal analytics

---

## Quick Launch Checklist

**Minimum to go live:**

- [ ] Stripe account created and configured
- [ ] Stripe subscription product created
- [ ] Webhook endpoint configured
- [ ] Production hosting set up
- [ ] Domain configured with SSL
- [ ] Environment variables set (SECRET_KEY, DEBUG=0, etc.)
- [ ] Database migrations run
- [ ] Test subscription works end-to-end
- [ ] Test invoice payment works
- [ ] Email configured (at least for password reset)
- [ ] Platform admin account created
- [ ] Terms of Service and Privacy Policy added
- [ ] Error tracking set up (Sentry)

**Nice to have:**

- [ ] PostgreSQL database
- [ ] Transactional email service
- [ ] Automated backups
- [ ] Monitoring/alerting
- [ ] User documentation
- [ ] Support system
- [ ] Analytics

---

## Launch Day Steps

1. **Final Testing:**
   - Test signup flow
   - Test subscription payment
   - Test invoice payment
   - Test all core features

2. **Go Live:**
   - Deploy to production
   - Verify all environment variables
   - Check webhook is receiving events
   - Monitor for errors

3. **First Customer:**
   - Create a test account
   - Complete subscription
   - Verify access works
   - Test invoice payment

4. **Monitor:**
   - Watch error logs
   - Monitor Stripe dashboard
   - Check webhook events
   - Respond to any issues quickly

---

## Post-Launch

**First Week:**
- Monitor error rates
- Check Stripe for failed payments
- Respond to customer questions
- Fix any critical bugs

**First Month:**
- Review analytics
- Gather customer feedback
- Optimize based on usage
- Plan feature improvements

---

## Support Resources

- **Stripe Support:** https://support.stripe.com
- **Django Docs:** https://docs.djangoproject.com
- **Your Platform Docs:** Check your hosting provider's docs

---

## Need Help?

If you encounter issues:
1. Check error logs
2. Review Stripe Dashboard for payment issues
3. Check webhook event logs in `StripeWebhookEvent` table
4. Test in Stripe test mode first
5. Contact support for your hosting platform
