"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "Field Ops Admin"
admin.site.site_title = "Field Ops"
admin.site.index_title = "Companies, users, and data — full control"

from config.platform_views import (
    platform_home, platform_enter, platform_exit,
    admin_users, admin_grant, admin_revoke
)
from config.marketing_views import marketing_home, terms_of_service, privacy_policy

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.auth_urls")),

    # Platform admin: list businesses and enter any dashboard
    path("platform/", platform_home, name="platform_home"),
    path("platform/enter/<int:business_id>/", platform_enter, name="platform_enter"),
    path("platform/exit/", platform_exit, name="platform_exit"),
    path("platform/admins/", admin_users, name="platform_admin_users"),
    path("platform/admins/<int:user_id>/grant/", admin_grant, name="platform_admin_grant"),
    path("platform/admins/<int:user_id>/revoke/", admin_revoke, name="platform_admin_revoke"),

    # Public marketing pages
    path("", marketing_home, name="marketing_home"),
    path("terms/", terms_of_service, name="terms_of_service"),
    path("privacy/", privacy_policy, name="privacy_policy"),

    # Main app (company dashboards)
    path("dashboard/", include("dashboard.urls")),
    path("billing/", include(("billing.urls", "billing"), namespace="billing")),
    path("clients/", include("customers.urls")),
    path("employees/", include("accounts.urls")),
    path("notifications/", include("accounts.notification_urls")),
    path("crews/", include("jobs.crew_urls")),
    path("jobs/", include("jobs.urls")),
    path("time/", include("time_tracking.urls")),
    path("settings/", include("businesses.urls")),
    path("subscription/", include("subscription.urls")),
    path("webhooks/stripe/", include("subscription.webhook_urls")),
    path("stripe-connect/", include("stripe_connect.urls")),
    path("quickbooks/", include(("quickbooks.urls", "quickbooks"), namespace="quickbooks")),
    path("financials/", include(("financials.urls", "financials"), namespace="financials")),
    path("estimator/", include("property_estimator.urls")),
]

# Diagnostic endpoints (only in DEBUG mode)
if settings.DEBUG:
    from config import diagnostic_views
    urlpatterns += [
        path("_diagnostic/database/", diagnostic_views.database_status, name="diagnostic_database"),
    ]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
