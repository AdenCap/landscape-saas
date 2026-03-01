"""
Health check endpoint to diagnose server errors.
Available at /health/ - shows database status and basic system info.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os


@csrf_exempt
@require_GET
def health_check(request):
    """
    Health check endpoint that shows database status and configuration.
    Useful for debugging server errors.
    """
    status = {
        "status": "ok",
        "database": {},
        "environment": {},
        "errors": [],
    }
    
    # Check database configuration
    db_config = settings.DATABASES.get('default', {})
    status["database"]["engine"] = db_config.get('ENGINE', 'unknown')
    status["database"]["name"] = db_config.get('NAME', 'unknown')
    status["database"]["host"] = db_config.get('HOST', 'unknown')
    
    # Check if DATABASE_URL is set (check all possible names)
    has_db_url = bool(
        os.environ.get('DATABASE_URL') or
        os.environ.get('SUPABASE_URL') or
        os.environ.get('SUPABASE_DATABASE_URL') or
        os.environ.get('POSTGRES_URL') or
        os.environ.get('POSTGRESQL_URL')
    )
    status["environment"]["has_database_url"] = has_db_url
    
    # Check which variable is set
    if os.environ.get('DATABASE_URL'):
        status["environment"]["database_url_source"] = "DATABASE_URL"
    elif os.environ.get('SUPABASE_URL'):
        status["environment"]["database_url_source"] = "SUPABASE_URL"
    elif os.environ.get('POSTGRES_URL'):
        status["environment"]["database_url_source"] = "POSTGRES_URL"
    else:
        status["environment"]["database_url_source"] = "none"
    
    # Try to connect to database
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            status["database"]["connection"] = "success"
            status["database"]["version"] = version[:100]  # Truncate for safety
            cursor.execute("SELECT 1;")
            status["database"]["test_query"] = "success"
    except Exception as e:
        status["database"]["connection"] = "failed"
        status["database"]["error"] = str(e)
        status["errors"].append(f"Database connection failed: {str(e)}")
        status["status"] = "error"
        
        # Add helpful diagnostic info
        error_str = str(e).lower()
        if "timeout" in error_str or "could not connect" in error_str:
            status["database"]["diagnostic"] = "Connection timeout - check Trusted Sources in DigitalOcean database settings. Your app component must be added to Trusted Sources."
        elif "password" in error_str or "authentication" in error_str:
            status["database"]["diagnostic"] = "Authentication failed - check DATABASE_URL password is correct. Get fresh connection string from Database → Connection Details."
        elif "ssl" in error_str:
            status["database"]["diagnostic"] = "SSL required - DigitalOcean requires SSL. The code should auto-add this, but verify DATABASE_URL includes sslmode=require"
        elif "does not exist" in error_str or ("database" in error_str and "exist" in error_str):
            status["database"]["diagnostic"] = "Database name might be wrong - check DATABASE_URL database name matches your DigitalOcean database"
    
    # Check if using SQLite in production
    if 'sqlite' in status["database"]["engine"].lower():
        is_prod = (
            os.environ.get("VERCEL") or
            os.environ.get("RAILWAY_ENVIRONMENT") or
            os.environ.get("RENDER") or
            not settings.DEBUG
        )
        if is_prod:
            status["errors"].append("Using SQLite in production - data will be lost on deployments!")
            status["status"] = "error"
    
    # Check critical settings
    if not settings.SECRET_KEY or settings.SECRET_KEY.startswith("django-insecure"):
        status["errors"].append("SECRET_KEY not properly set")
        status["status"] = "warning"
    
    return JsonResponse(status, json_dumps_params={'indent': 2})
