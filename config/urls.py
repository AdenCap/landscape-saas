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
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "Field Ops Admin"
admin.site.site_title = "Field Ops"
admin.site.index_title = "Companies, users, and data — full control"

from config.platform_views import (
    platform_home, platform_enter, platform_enter_demo, platform_set_plan, platform_apply_plan_recommendations, platform_toggle_free_access, platform_exit,
    admin_users, admin_grant, admin_revoke
)
from config.marketing_views import (
    marketing_home, marketing_features, marketing_feature_detail, marketing_automation, marketing_pricing,
    terms_of_service, privacy_policy, robots_txt, sitemap_xml,
)
from config.db_check import db_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/db-check/", db_check),
    path("accounts/", include("accounts.auth_urls")),

    # Platform admin: list businesses and enter any dashboard
    path("platform/", platform_home, name="platform_home"),
    path("platform/enter/<int:business_id>/", platform_enter, name="platform_enter"),
    path("platform/enter-demo/", platform_enter_demo, name="platform_enter_demo"),
    path("platform/set-plan/<int:business_id>/", platform_set_plan, name="platform_set_plan"),
    path("platform/apply-plan-recommendations/", platform_apply_plan_recommendations, name="platform_apply_plan_recommendations"),
    path("platform/toggle-free-access/<int:business_id>/", platform_toggle_free_access, name="platform_toggle_free_access"),
    path("platform/exit/", platform_exit, name="platform_exit"),
    path("platform/admins/", admin_users, name="platform_admin_users"),
    path("platform/admins/<int:user_id>/grant/", admin_grant, name="platform_admin_grant"),
    path("platform/admins/<int:user_id>/revoke/", admin_revoke, name="platform_admin_revoke"),

    # Public marketing pages
    path("", marketing_home, name="marketing_home"),
    path("features/", marketing_features, name="marketing_features"),
    path("features/<slug:slug>/", marketing_feature_detail, name="marketing_feature_detail"),
    path("automation/", marketing_automation, name="marketing_automation"),
    path("pricing/", marketing_pricing, name="marketing_pricing"),
    path("terms/", terms_of_service, name="terms_of_service"),
    path("privacy/", privacy_policy, name="privacy_policy"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),

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
    path("financials/", include(("financials.urls", "financials"), namespace="financials")),
    path("estimator/", include("property_estimator.urls")),
    path("quickbooks/", include("quickbooks.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
