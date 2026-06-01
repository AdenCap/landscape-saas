from django.conf import settings


def app_urls(_request):
    return {
        "APP_BASE_URL": getattr(settings, "APP_BASE_URL", "https://app.fieldlgx.com").rstrip("/"),
        "PUBLIC_SITE_URL": getattr(settings, "PUBLIC_SITE_URL", "https://fieldlgx.com").rstrip("/"),
    }
