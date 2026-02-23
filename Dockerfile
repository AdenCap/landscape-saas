# Dockerfile for Django app (e.g. Kubernetes, Fly.io, or any container host).
# Build: docker build -t landscape-saas .
# Run:   docker run -p 8080:8080 -e DJANGO_SECRET_KEY=... -e DATABASE_URL=... landscape-saas

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8080

RUN chmod +x run.sh
# Must specify the WSGI app module (config.wsgi:application); otherwise Gunicorn errors: "No application module specified."
# run.sh uses PORT from env (default 8080) so readiness probes on 8080 succeed.
CMD ["./run.sh"]
