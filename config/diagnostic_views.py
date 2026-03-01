"""
Diagnostic views to help troubleshoot database and configuration issues.
Only available when DEBUG=True for security.
"""
import os
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_GET
def database_status(request):
    """
    Diagnostic endpoint to check database configuration and connection.
    Only available when DEBUG=True.
    """
    if not settings.DEBUG:
        return JsonResponse({"error": "Diagnostic endpoints only available in DEBUG mode"}, status=403)
    
    from django.db import connection
    from config.database_check import check_database_persistence
    
    result = {
        "database_engine": settings.DATABASES['default'].get('ENGINE', ''),
        "database_name": settings.DATABASES['default'].get('NAME', ''),
        "database_host": settings.DATABASES['default'].get('HOST', ''),
        "database_port": settings.DATABASES['default'].get('PORT', ''),
        "has_database_url": bool(os.environ.get('DATABASE_URL')),
    }
    
    # Check persistence
    is_safe, warning = check_database_persistence()
    result["is_safe"] = is_safe
    result["warning"] = warning
    
    # Test connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            result["connection_status"] = "success"
            result["database_version"] = version[:100]  # Truncate for safety
    except Exception as e:
        result["connection_status"] = "failed"
        result["connection_error"] = str(e)
    
    return JsonResponse(result, safe=False)
