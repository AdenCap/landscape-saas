#!/bin/sh
# Start Gunicorn with the Django WSGI app. Bind to 8080 so health checks succeed.
# PYTHONPATH ensures "config.wsgi" is found when run from repo root.
export PORT="${PORT:-8080}"
export PYTHONPATH="${PYTHONPATH:-.}:."
exec gunicorn config.wsgi:application --bind "0.0.0.0:8080" --workers 1 --timeout 120
