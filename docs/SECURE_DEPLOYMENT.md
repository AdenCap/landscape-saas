# Secure deployment guide: publish to your own server

This guide walks you through deploying the app to **your own server** (VPS) with security best practices so you can fully test the software over the internet.

---

## Overview

1. **Server hardening** — SSH, firewall, updates  
2. **Secrets & environment** — never commit production keys  
3. **Django production settings** — already wired; you set env vars  
4. **Database** — PostgreSQL recommended for production  
5. **HTTPS** — SSL/TLS with Let's Encrypt  
6. **App server** — Gunicorn + Nginx (reverse proxy + static)  
7. **Process management** — systemd  
8. **Ongoing** — backups, updates, logging  

---

## 1. Server setup and hardening

### 1.1 Create a VPS

- Use a provider: **DigitalOcean**, **Linode**, **Hetzner**, **Vultr**, or **AWS Lightsail**.
- Pick Ubuntu 22.04 LTS (or 24.04).
- Create a non-root user with sudo (e.g. `deploy`).

### 1.2 SSH hardening

On your **local machine**, use a key (no password login on server):

```bash
# Generate key if you don't have one
ssh-keygen -t ed25519 -C "your-email@example.com"
```

On the **server**, as root or your sudo user:

```bash
# Add your public key to the deploy user
mkdir -p ~/.ssh
echo "YOUR_PUBLIC_KEY_CONTENT" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

Then disable password and root login (do this only after confirming key login works):

```bash
sudo nano /etc/ssh/sshd_config
```

Set (or add):

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Restart SSH: `sudo systemctl restart sshd`

### 1.3 Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for Let's Encrypt and redirect)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

### 1.4 Updates and basics

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential python3-pip python3-venv libpq-dev nginx certbot python3-certbot-nginx git
```

---

## 2. Secrets and environment variables

**Never commit production secrets to Git.** Use a single `.env` file on the server (or your platform’s env vars) and load it into the app.

### 2.1 Generate a strong SECRET_KEY

On your **local machine** (or server):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Copy the output; you’ll set it as `DJANGO_SECRET_KEY` on the server.

### 2.2 Create `.env` on the server

On the server, in the app directory (e.g. `/home/deploy/landscape-saas`):

```bash
nano .env
```

Add (replace with your real values):

```env
# Required for production
DJANGO_SECRET_KEY=your-generated-secret-key-here
DJANGO_DEBUG=0
ALLOWED_HOSTS=fieldlgx.com,www.fieldlgx.com
CSRF_TRUSTED_ORIGINS=https://fieldlgx.com,https://www.fieldlgx.com

# If using PostgreSQL (recommended)
DATABASE_URL=postgresql://dbuser:dbpassword@localhost:5432/landscape_db

# Optional
# MAPBOX_ACCESS_TOKEN=...
# GOOGLE_MAPS_API_KEY=...
# QUICKBOOKS_CLIENT_ID=...
# QUICKBOOKS_CLIENT_SECRET=...
# QUICKBOOKS_REDIRECT_URI=https://fieldlgx.com/quickbooks/callback/
```

Secure the file:

```bash
chmod 600 .env
```

The app already loads `.env` via `python-dotenv` in `config/settings.py`. For Gunicorn, you can load it in the systemd unit (see below).

---

## 3. Django production checklist (what the app already does)

When `DJANGO_DEBUG=0` and you set the env vars above, the app automatically:

- Uses your `DJANGO_SECRET_KEY` and restricts `ALLOWED_HOSTS`
- Enforces HTTPS redirect, HSTS, secure cookies, and security headers
- Uses `CSRF_TRUSTED_ORIGINS` for HTTPS CSRF

You must set:

| Variable | Example | Notes |
|----------|---------|--------|
| `DJANGO_SECRET_KEY` | (50+ char random) | **Required**; generate with `secrets.token_urlsafe(50)` |
| `DJANGO_DEBUG` | `0` | **Required** in production |
| `ALLOWED_HOSTS` | `fieldlgx.com,www.fieldlgx.com` | Comma-separated, no spaces |
| `CSRF_TRUSTED_ORIGINS` | `https://fieldlgx.com,https://www.fieldlgx.com` | Must use `https://` |

---

## 4. Database: PostgreSQL (recommended for production)

SQLite is fine for very small single-worker deploys; for a “real” test server use PostgreSQL.

### 4.1 Install and create DB

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres psql
```

In PostgreSQL:

```sql
CREATE USER landscape_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE landscape_db OWNER landscape_user;
\q
```

### 4.2 Set DATABASE_URL in `.env`

```env
DATABASE_URL=postgresql://landscape_user:choose-a-strong-password@localhost:5432/landscape_db
```

- If the password contains `@`, `#`, or `%`, URL-encode it.
- For a **managed database** (e.g. AWS RDS, DigitalOcean Managed DB), add `?sslmode=require` to the URL if the provider requires SSL.

### 4.3 Run migrations on the server

```bash
cd /home/deploy/landscape-saas
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser   # for /admin/
python manage.py collectstatic --noinput
```

---

## 5. HTTPS with Let's Encrypt

Use Certbot so the site is served over HTTPS.

### 5.1 Point your domain to the server

Create an A record (and optionally AAAA for IPv6) for `fieldlgx.com` and `www.fieldlgx.com` to your server’s IP.

### 5.2 Get the certificate

**Temporary Nginx config** (so Certbot can validate):

```bash
sudo nano /etc/nginx/sites-available/landscape
```

Paste (replace `fieldlgx.com`):

```nginx
server {
    listen 80;
    server_name fieldlgx.com www.fieldlgx.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/landscape /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Then run Certbot:

```bash
sudo certbot --nginx -d fieldlgx.com -d www.fieldlgx.com
```

Certbot will adjust the Nginx config to use HTTPS and redirect HTTP → HTTPS.

### 5.3 Auto-renewal

```bash
sudo certbot renew --dry-run
```

Cron is usually installed by Certbot for renewal; if not, add a cron job for `certbot renew`.

---

## 6. Application server: Gunicorn + Nginx

### 6.1 App directory and virtualenv on server

```bash
cd /home/deploy
git clone https://github.com/YourOrg/landscape-saas.git
cd landscape-saas
python3 -venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Load `.env` and run Gunicorn manually to test:

```bash
set -a && source .env && set +a
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2
```

Visit `http://fieldlgx.com` (or via Nginx proxy); then stop with Ctrl+C.

### 6.2 systemd unit (so the app runs on boot and restarts on failure)

Create a unit that loads `.env` and runs Gunicorn:

```bash
sudo nano /etc/systemd/system/landscape.service
```

Paste (adjust paths and user):

```ini
[Unit]
Description=Landscape SaaS Gunicorn
After=network.target postgresql.service

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/landscape-saas
EnvironmentFile=/home/deploy/landscape-saas/.env
ExecStart=/home/deploy/landscape-saas/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 120
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable landscape
sudo systemctl start landscape
sudo systemctl status landscape
```

### 6.3 Nginx (final) as reverse proxy + static files

Update the Nginx site so it proxies to Gunicorn and serves static files (after Certbot, you’ll have an `ssl_server` block). Example full config:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name fieldlgx.com www.fieldlgx.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fieldlgx.com www.fieldlgx.com;

    # Certbot manages these paths
    ssl_certificate /etc/letsencrypt/live/fieldlgx.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fieldlgx.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 20M;

    location /static/ {
        alias /home/deploy/landscape-saas/staticfiles/;
    }
    location /media/ {
        alias /home/deploy/landscape-saas/media/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
}
```

Reload Nginx:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. Deploy and update workflow

From your **local machine**:

```bash
git push origin main
```

On the **server**:

```bash
cd /home/deploy/landscape-saas
git pull
source venv/bin/activate
pip install -r requirements.txt
set -a && source .env && set +a
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart landscape
```

(You can turn this into a small deploy script or use a CI/CD job that SSHs and runs these commands.)

---

## 8. Security checklist summary

| Item | Done |
|------|------|
| SSH key-only login; password login disabled | ☐ |
| UFW: only 22, 80, 443 open | ☐ |
| `DJANGO_DEBUG=0` | ☐ |
| Strong `DJANGO_SECRET_KEY` (not default) | ☐ |
| `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set for your domain | ☐ |
| HTTPS (Let's Encrypt); HTTP redirects to HTTPS | ☐ |
| `.env` not in Git; `chmod 600 .env` on server | ☐ |
| PostgreSQL used in production (optional but recommended) | ☐ |
| Gunicorn bound to 127.0.0.1 (Nginx proxies) | ☐ |
| Regular `apt update && apt upgrade` and Certbot renewal | ☐ |

---

## 9. Optional: backups

- **Database:** `pg_dump` (PostgreSQL) or copy `db.sqlite3` (SQLite) to a safe location; run daily via cron.
- **Media/uploads:** Backup the `media/` directory.
- Store backups off the server (e.g. S3, Backblaze, or another machine).

---

## 10. Optional: managed / PaaS (no server to harden)

If you prefer not to manage a server:

- **Railway / Render / Fly.io:** Connect the repo, set the same env vars (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, optional `DATABASE_URL`). They provide HTTPS and often a database.
- See the main **DEPLOYMENT.md** in the project root for platform-specific steps.

Using this guide, you can publish the app to your own server and test it over the internet with security best practices in place.
