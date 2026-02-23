#!/bin/sh
# Start Gunicorn with the Django WSGI app. Use PORT from env (e.g. 8080 for k8s/Railway/Render).
export PORT="${PORT:-8080}"
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT}" --workers 1 --timeout 120
