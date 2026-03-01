"""
Print which database the app is using. Run after deploy to verify Supabase is connected.

  python manage.py show_database

On Digital Ocean: use Run Command or a one-off job with this command.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = "Show which database backend and host are in use (for verifying Supabase in production)."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        engine = db.get("ENGINE", "")
        if "postgresql" in engine:
            host = db.get("HOST", "?")
            name = db.get("NAME", "?")
            self.stdout.write(
                self.style.SUCCESS(f"Database: PostgreSQL at {host} / {name}")
            )
            # Quick connectivity check
            try:
                with connection.cursor() as cur:
                    cur.execute("SELECT 1")
                self.stdout.write(self.style.SUCCESS("Connection test: OK"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Connection test failed: {e}"))
        else:
            path = db.get("NAME", "?")
            self.stdout.write(
                self.style.WARNING(f"Database: SQLite at {path}")
            )
            self.stdout.write(
                self.style.WARNING(
                    "Data will NOT persist across redeploys. Set POSTGRES_URL (Supabase URI) at runtime."
                )
            )
