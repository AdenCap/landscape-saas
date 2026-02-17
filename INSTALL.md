# Landscape SaaS – Installation Steps

## 1. Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended)
- **Git** (if cloning the repo)

Check Python:
```bash
python3 --version
```

---

## 2. Get the project

If you already have the project folder, skip to step 3.

```bash
cd ~/Desktop/Landscape\ Software
# or wherever you keep the project
cd landscape-saas
```

---

## 3. Create a virtual environment

```bash
cd landscape-saas
python3 -m venv venv
```

Activate it:

- **macOS/Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows (Command Prompt):**
  ```cmd
  venv\Scripts\activate.bat
  ```
- **Windows (PowerShell):**
  ```powershell
  venv\Scripts\Activate.ps1
  ```

You should see `(venv)` in your prompt.

---

## 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If you get **SSL certificate errors** (e.g. on macOS):

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

This installs Django, psycopg2-binary, and all other packages in `requirements.txt`.

---

## 5. Environment variables (optional)

Copy the example env file and edit if you need QuickBooks, Mapbox, or Google Maps:

```bash
cp .env.example .env
```

Edit `.env` and set any values you need (e.g. `GOOGLE_MAPS_API_KEY`, `QUICKBOOKS_*`). The app runs without `.env`; it’s only for optional integrations and overrides.

---

## 6. Database

### Option A: SQLite (default, no extra setup)

The project is configured to use SQLite by default. Run migrations:

```bash
python manage.py migrate
```

### Option B: PostgreSQL

1. Install and start PostgreSQL on your machine.
2. Create a database, e.g.:
   ```bash
   createdb landscape_saas
   ```
3. In `config/settings.py`, set `DATABASES` to use PostgreSQL, or use a separate settings file / environment variables that point to PostgreSQL (engine `django.db.backends.postgresql`, with `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`).
4. Install the driver (already in `requirements.txt`):
   ```bash
   pip install psycopg2-binary
   ```
5. Run migrations:
   ```bash
   python manage.py migrate
   ```

---

## 7. Create a superuser (optional)

To access the Django admin:

```bash
python manage.py createsuperuser
```

Enter username, email, and password when prompted.

---

## 8. Run the development server

```bash
python manage.py runserver
```

Open in a browser:

- **Owner dashboard (home):** http://127.0.0.1:8000/
- **Dashboard:** http://127.0.0.1:8000/dashboard
- **Admin:** http://127.0.0.1:8000/admin/
- **Billing:** http://127.0.0.1:8000/billing/
- **Jobs:** http://127.0.0.1:8000/jobs/

---

## Quick checklist

| Step | Command / action |
|------|-------------------|
| 1 | Python 3.10+ installed |
| 2 | In project folder `landscape-saas` |
| 3 | `python3 -m venv venv` then `source venv/bin/activate` (or Windows equivalent) |
| 4 | `pip install -r requirements.txt` (use `--trusted-host` if SSL errors) |
| 5 | (Optional) `cp .env.example .env` and edit |
| 6 | `python manage.py migrate` |
| 7 | (Optional) `python manage.py createsuperuser` |
| 8 | `python manage.py runserver` → open http://127.0.0.1:8000/ |

---

## Troubleshooting

- **“No module named psycopg2”**  
  Install the driver **into the same environment** you use to run the server:

  1. **Use the project venv explicitly** (recommended):
     ```bash
     # From project root (landscape-saas)
     ./venv/bin/pip install psycopg2-binary
     ```
     If you get SSL errors:
     ```bash
     ./venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org psycopg2-binary
     ```
     Or run the script:
     ```bash
     chmod +x install_psycopg2.sh
     ./install_psycopg2.sh
     ```

  2. **Run the server with the venv’s Python** so the same packages are used:
     ```bash
     source venv/bin/activate
     python manage.py runserver
     ```
     Or without activating:
     ```bash
     ./venv/bin/python manage.py runserver
     ```

  The project is configured to use **SQLite** by default, so Django only needs psycopg2 if you switch the database to PostgreSQL (e.g. in production or via another settings file).

- **“No module named …” (other)**  
  Ensure the venv is activated and run:  
  `pip install -r requirements.txt`

- **Migrations out of date**  
  After pulling code:  
  `python manage.py migrate`

- **Port 8000 in use**  
  Use another port:  
  `python manage.py runserver 8080`
