#!/bin/sh
# Vercel build: install deps, migrate, collectstatic.
# Do not set Output Directory in Vercel so api/wsgi.py is still deployed as a serverless function.
set -e
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
