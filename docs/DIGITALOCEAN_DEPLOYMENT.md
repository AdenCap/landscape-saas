# Deploying to DigitalOcean App Platform

This guide covers deploying Field Ops to DigitalOcean App Platform and configuring environment variables.

## Step 1: Create App on DigitalOcean

1. **Sign in to DigitalOcean:**
   - Go to https://cloud.digitalocean.com
   - Sign in or create account

2. **Create New App:**
   - Click "Create" → "Apps"
   - Choose "GitHub" as source
   - Select your repository
   - Choose branch (usually `main`)

3. **Configure App:**
   - **Name:** field-ops (or your choice)
   - **Region:** Choose closest to your users
   - **Plan:** Basic ($12/month) or Professional

## Step 2: Configure Build Settings

**Build Command:**
```bash
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

**Important:** Make sure migrations run during build so the database schema is created!

**Run Command:**
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8080
```

**OR** if you have a `Procfile` or `run.sh`, DigitalOcean will detect it automatically.

## Step 3: Add Environment Variables

**This is where you put all your environment variables:**

1. **In DigitalOcean Dashboard:**
   - Go to your App
   - Click "Settings" tab
   - Scroll down to "App-Level Environment Variables"
   - Click "Edit" or "Add Variable"

2. **Add Each Variable:**
   Click "Add Variable" for each one:

   ```
   Key: DJANGO_SECRET_KEY
   Value: <paste-your-generated-key>
   Scope: Run Time
   ```

   ```
   Key: DJANGO_DEBUG
   Value: 0
   Scope: Run Time
   ```

   ```
   Key: ALLOWED_HOSTS
   Value: yourdomain.com,www.yourdomain.com
   Scope: Run Time
   ```

   ```
   Key: CSRF_TRUSTED_ORIGINS
   Value: https://yourdomain.com,https://www.yourdomain.com
   Scope: Run Time
   ```

   ```
   Key: STRIPE_SECRET_KEY
   Value: sk_live_...
   Scope: Run Time
   ```

   ```
   Key: STRIPE_PUBLISHABLE_KEY
   Value: pk_live_...
   Scope: Run Time
   ```

   ```
   Key: STRIPE_WEBHOOK_SECRET
   Value: whsec_...
   Scope: Run Time
   ```

   ```
   Key: STRIPE_SUBSCRIPTION_PRICE_ID
   Value: price_...
   Scope: Run Time
   ```

3. **For Each Variable:**
   - **Key:** The variable name (exactly as shown)
   - **Value:** Your actual value (no quotes needed)
   - **Scope:** Choose "Run Time" (available when app runs)
   - Click "Save" after each one

## Step 4: Add Database (Optional but Recommended)

**If using PostgreSQL:**

1. In your App, go to "Components" tab
2. Click "Add Component" → "Database"
3. Choose "PostgreSQL"
4. Select plan (Basic $15/month or Dev $7/month)
5. DigitalOcean will automatically set `DATABASE_URL` environment variable

**If using SQLite:**
- No database component needed
- Ensure you have persistent storage (DigitalOcean handles this)

## Step 5: Configure Domain

1. **In App Settings:**
   - Go to "Domains" tab
   - Click "Add Domain"
   - Enter your domain (e.g., `yourdomain.com`)
   - Follow DNS instructions to point your domain

2. **Update Environment Variables:**
   - After domain is connected, update:
     - `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
     - `CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`

## Step 6: Deploy

1. **Review Settings:**
   - Check all environment variables are set
   - Verify build and run commands
   - Confirm domain is configured

2. **Deploy:**
   - Click "Deploy" or push to GitHub (auto-deploys)
   - Watch build logs for errors
   - Wait for deployment to complete

3. **Verify:**
   - Visit your app URL
   - Test signup
   - Test subscription

## Step 7: Set Up Webhook

**After deployment, configure Stripe webhook:**

1. **Get Your Webhook URL:**
   - Your app URL: `https://yourdomain.com`
   - Webhook endpoint: `https://yourdomain.com/webhooks/stripe/`

2. **In Stripe Dashboard:**
   - Go to Developers → Webhooks
   - Add endpoint: `https://yourdomain.com/webhooks/stripe/`
   - Select events (see STRIPE_SETUP.md)
   - Copy signing secret

3. **Add to DigitalOcean:**
   - Go back to App → Settings → Environment Variables
   - Add `STRIPE_WEBHOOK_SECRET` with the signing secret
   - Redeploy (or it will auto-redeploy)

## Visual Guide: Where to Find Environment Variables

```
DigitalOcean Dashboard
  └── Your App
      └── Settings Tab
          └── App-Level Environment Variables
              └── [Click "Edit" or "Add Variable"]
                  ├── Key: DJANGO_SECRET_KEY
                  ├── Value: <your-value>
                  └── Scope: Run Time
```

## Important Notes

1. **No Quotes Needed:**
   - Don't wrap values in quotes
   - Just paste the value directly

2. **Case Sensitive:**
   - Variable names are case-sensitive
   - Use exactly: `DJANGO_SECRET_KEY` not `django_secret_key`

3. **Redeploy After Changes:**
   - After adding/updating env vars, app will auto-redeploy
   - Or manually trigger redeploy

4. **Secrets:**
   - Environment variables are encrypted at rest
   - Never commit secrets to GitHub

## Troubleshooting

**"App won't start"**
- Check run command is correct
- Verify all required env vars are set
- Check build logs for errors

**"Webhook not working"**
- Verify `STRIPE_WEBHOOK_SECRET` is set correctly
- Check webhook URL in Stripe Dashboard matches your domain
- Check app logs for webhook errors

**"Can't access app"**
- Verify `ALLOWED_HOSTS` includes your domain
- Check `CSRF_TRUSTED_ORIGINS` includes HTTPS URL
- Ensure domain DNS is pointing correctly

## Cost Estimate

- **App Platform:** $12/month (Basic) or $24/month (Professional)
- **PostgreSQL (optional):** $15/month (Basic) or $7/month (Dev)
- **Total:** ~$27-39/month to start

## Next Steps

After deployment:
1. Test signup flow
2. Test subscription payment
3. Test invoice payment
4. Monitor for errors
5. Set up backups (DigitalOcean offers automated backups)

---

**Need Help?**
- DigitalOcean Docs: https://docs.digitalocean.com/products/app-platform/
- DigitalOcean Support: Available in dashboard
