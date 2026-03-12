# Deployment & testing plan

Use this as a linear checklist to get the app from your machine to a live server so you can fully test the software.

---

## VPS + domain: ordered checklist

Use this path when you have (or will have) a **VPS** and a **domain**. Replace `YOUR_DOMAIN`, `YOUR_VPS_IP`, and `deploy` with your real values.

### A. On your own machine

1. **Push latest code**
   ```bash
   git push origin main
   ```

2. **Generate and save the secret key** (store in a password manager):
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

3. **Get your VPS IP** from your provider (DigitalOcean, Linode, Hetzner, Vultr, etc.) after creating the droplet/server.

4. **Point your domain to the VPS**
   - At your domain registrar (or DNS provider), add an **A record**: host `@` (or `fieldlgx.com`) → `YOUR_VPS_IP`.
   - Add another A record for `www` → `YOUR_VPS_IP` if you want `www.fieldlgx.com`.
   - Wait a few minutes (up to 48 hours in rare cases) for DNS to propagate.

### B. On the VPS (first time)

5. **Log in and create deploy user** (if the provider gave you root):
   ```bash
   ssh root@YOUR_VPS_IP
   adduser deploy
   usermod -aG sudo deploy
   su - deploy
   ```

6. **Add your SSH key** so you can log in as `deploy` without a password:
   ```bash
   mkdir -p ~/.ssh
   nano ~/.ssh/authorized_keys
   # Paste your public key (e.g. from cat ~/.ssh/id_ed25519.pub on your Mac), save and exit
   chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
   ```
   Then from your Mac: `ssh deploy@YOUR_VPS_IP` to confirm it works.

7. **Harden SSH** (only after step 6 works):
   ```bash
   sudo nano /etc/ssh/sshd_config
   # Set: PermitRootLogin no, PasswordAuthentication no
   sudo systemctl restart sshd
   ```

8. **Firewall**
   ```bash
   sudo ufw default deny incoming
   sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
   sudo ufw enable
   ```

9. **Install packages**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y nginx certbot python3-certbot-nginx postgresql postgresql-contrib git python3-venv python3-pip libpq-dev
   ```

10. **PostgreSQL: create DB and user**
    ```bash
    sudo -u postgres psql
    ```
    In `psql`:
    ```sql
    CREATE USER landscape_user WITH PASSWORD 'CHOOSE_A_STRONG_PASSWORD';
    CREATE DATABASE landscape_db OWNER landscape_user;
    \q
    ```

11. **Clone app and install Python deps**
    ```bash
    cd ~
    git clone https://github.com/AdenCap/landscape-saas.git
    cd landscape-saas
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

12. **Create `.env`** (use the secret key from step 2 and your domain):
    ```bash
    nano .env
    ```
    Paste (replace placeholders):
    ```env
    DJANGO_SECRET_KEY=paste_the_long_secret_from_step_2
    DJANGO_DEBUG=0
    ALLOWED_HOSTS=YOUR_DOMAIN,www.YOUR_DOMAIN
    CSRF_TRUSTED_ORIGINS=https://YOUR_DOMAIN,https://www.YOUR_DOMAIN
    DATABASE_URL=postgresql://landscape_user:CHOOSE_A_STRONG_PASSWORD@localhost:5432/landscape_db
    ```
    Save, then: `chmod 600 .env`

13. **Migrations, superuser, static files**
    ```bash
    set -a && source .env && set +a
    python manage.py migrate
    python manage.py createsuperuser
    python manage.py collectstatic --noinput
    ```

14. **Test Gunicorn**
    ```bash
    gunicorn config.wsgi:application --bind 127.0.0.1:8000
    ```
    In another terminal: `curl http://127.0.0.1:8000` or open from the server. Stop with Ctrl+C.

15. **Systemd service** so the app runs on boot:
    ```bash
    sudo nano /etc/systemd/system/landscape.service
    ```
    Paste (fix paths if your user or path is different):
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
    Then:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable landscape
    sudo systemctl start landscape
    ```

16. **Nginx: temporary config** (so Certbot can get a certificate):
    ```bash
    sudo nano /etc/nginx/sites-available/landscape
    ```
    Paste (replace YOUR_DOMAIN):
    ```nginx
    server {
        listen 80;
        server_name YOUR_DOMAIN www.YOUR_DOMAIN;
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```
    Enable and reload:
    ```bash
    sudo ln -s /etc/nginx/sites-available/landscape /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    ```

17. **Get SSL certificate**
    ```bash
    sudo certbot --nginx -d YOUR_DOMAIN -d www.YOUR_DOMAIN
    ```
    Follow prompts (email, agree to terms). Certbot will turn on HTTPS and redirect HTTP → HTTPS.

18. **Nginx: serve static/media** (optional but recommended). Edit the same file; Certbot will have added an `ssl_server` block. Add inside the `server { listen 443 ssl ... }` block:
    ```nginx
    location /static/ {
        alias /home/deploy/landscape-saas/staticfiles/;
    }
    location /media/ {
        alias /home/deploy/landscape-saas/media/;
    }
    ```
    Then: `sudo nginx -t && sudo systemctl reload nginx`

### C. Go live

19. **Open in browser:** `https://YOUR_DOMAIN` — you should see the app over HTTPS.

20. **Test:** Sign up or log in as superuser, click through dashboard, jobs, calendar, time, settings.

21. **Later: deploy updates** (on the VPS):
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

---

## Phase 1: Before you touch the server

| # | Task | Notes |
|---|------|--------|
| 1.1 | Push latest code to GitHub | `git add -A && git commit -m "..." && git push` so the server can pull the same code. |
| 1.2 | Choose hosting | **VPS** (DigitalOcean, Linode, Hetzner, etc.) for full control, or **PaaS** (Railway, Render) for less ops. |
| 1.3 | Buy or pick a domain (optional) | e.g. `landscape.yourcompany.com` or use the host’s URL (e.g. `yourapp.railway.app`). |
| 1.4 | Generate a production secret key | Run: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` and store it somewhere safe (password manager). You’ll set it as `DJANGO_SECRET_KEY` on the server. |

---

## Phase 2: Server (VPS) setup

*Skip to Phase 3 if you use Railway/Render and follow their “connect repo + set env vars” flow instead.*

| # | Task | Notes |
|---|------|--------|
| 2.1 | Create the VPS | Ubuntu 22.04 or 24.04; create a non-root user (e.g. `deploy`) with sudo. |
| 2.2 | Add your SSH key to the server | So you can log in without a password. |
| 2.3 | Harden SSH | In `sshd_config`: `PermitRootLogin no`, `PasswordAuthentication no`. Restart SSH only after confirming key login works. |
| 2.4 | Configure firewall | `ufw allow 22,80,443` then `ufw enable`. |
| 2.5 | Install base packages | `apt update && apt upgrade`, then install: `nginx`, `certbot` (and `python3-certbot-nginx`), `postgresql`, `git`, `python3-venv`, `python3-pip`, `libpq-dev`. |

---

## Phase 3: App and environment on the server

| # | Task | Notes |
|---|------|--------|
| 3.1 | Clone the repo | e.g. `git clone https://github.com/YourOrg/landscape-saas.git` into `/home/deploy/landscape-saas`. |
| 3.2 | Create virtualenv and install deps | `cd landscape-saas && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`. |
| 3.3 | Create `.env` on the server | Set at least: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`. Never commit `.env`. |
| 3.4 | Database choice | **SQLite (simplest):** no extra setup; ensure app directory is writable. **PostgreSQL (recommended):** create DB and user, set `DATABASE_URL` in `.env`. |
| 3.5 | Run migrations | `python manage.py migrate`. |
| 3.6 | Create superuser | `python manage.py createsuperuser` for `/admin/`. |
| 3.7 | Collect static files | `python manage.py collectstatic --noinput`. |

---

## Phase 4: HTTPS and web server (VPS)

| # | Task | Notes |
|---|------|--------|
| 4.1 | Point domain to server | Create A (and optionally AAAA) records for your domain to the VPS IP. |
| 4.2 | Temporary Nginx config | Proxy HTTP to Gunicorn (e.g. `proxy_pass http://127.0.0.1:8000`) so Certbot can reach the app. |
| 4.3 | Get SSL certificate | `sudo certbot --nginx -d fieldlgx.com -d www.fieldlgx.com`. |
| 4.4 | Run app with Gunicorn | Test: `gunicorn config.wsgi:application --bind 127.0.0.1:8000`. Then add a systemd unit so it runs on boot and restarts on failure. |
| 4.5 | Final Nginx config | Serve `/static/` and `/media/` from disk; proxy everything else to Gunicorn. Redirect HTTP → HTTPS. Reload Nginx. |

---

## Phase 5: Go live and smoke test

| # | Task | Notes |
|---|------|--------|
| 5.1 | Restart app and Nginx | `sudo systemctl restart landscape` (or your service name), `sudo systemctl reload nginx`. |
| 5.2 | Visit the site over HTTPS | Open `https://fieldlgx.com`; confirm no certificate warnings. |
| 5.3 | Sign up / log in | Create a new account or log in as superuser; confirm login and redirects work. |
| 5.4 | Quick test of main flows | Dashboard, create a job, calendar, time clock, billing (if configured), settings. Note any errors or missing env vars (e.g. QuickBooks, Maps, Mapbox). |
| 5.5 | Check admin | Log in to `https://fieldlgx.com/admin/` with the superuser account. |

---

## Phase 6: Ongoing

| # | Task | Notes |
|---|------|--------|
| 6.1 | Deploy updates | On server: `git pull`, `pip install -r requirements.txt`, `migrate`, `collectstatic`, restart Gunicorn. |
| 6.2 | Backups | Back up database (e.g. `pg_dump` or copy `db.sqlite3`) and `media/`; store off-server. |
| 6.3 | Monitor and patch | Keep OS and Nginx updated; ensure Certbot renewal runs (e.g. `certbot renew --dry-run`). |

---

## If you use Railway or Render instead of a VPS

- Do **Phase 1** (push code, secret key, domain if you want).
- In the dashboard: connect repo, add env vars (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`), set start command to `gunicorn config.wsgi:application`.
- Add a PostgreSQL add-on if you want; set `DATABASE_URL` from the add-on.
- Run migrations (one-off shell or CLI) and create superuser if needed.
- Then do **Phase 5** smoke tests against the provided URL (or your custom domain).

---

## Reference

- **Full secure server steps:** [docs/SECURE_DEPLOYMENT.md](SECURE_DEPLOYMENT.md)
- **PaaS / general deploy:** [DEPLOYMENT.md](../DEPLOYMENT.md) (project root)
