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
from django.views.generic import RedirectView

admin.site.site_header = "FIELDLGX Admin"
admin.site.site_title = "FIELDLGX"
admin.site.index_title = "Companies, users, and data — full control"

from config.platform_views import (
    platform_home, platform_enter, platform_enter_demo, platform_set_plan, platform_apply_plan_recommendations, platform_toggle_free_access, platform_exit,
    admin_users, admin_grant, admin_revoke
)
from customers.views import public_booking
from config.marketing_views import (
    marketing_home, marketing_features, marketing_feature_detail, marketing_automation, marketing_pricing,
    terms_of_service, privacy_policy, robots_txt, sitemap_xml, vertical_landing,
)
from config.db_check import db_check
from config.media_views import uploaded_media

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.ico", permanent=True)),
    path("uploads/<path:path>", uploaded_media, name="uploaded_media"),
    path("admin/", admin.site.urls),
    path("api/db-check/", db_check),
    path("accounts/", include("accounts.auth_urls")),
    path("accounts/social/", include("allauth.urls")),

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

    # Vertical landing pages
    path("hvac/", vertical_landing, {"vertical": "hvac"}, name="vertical_hvac"),
    path("plumbing/", vertical_landing, {"vertical": "plumbing"}, name="vertical_plumbing"),
    path("electrical/", vertical_landing, {"vertical": "electrical"}, name="vertical_electrical"),
    path("cleaning/", vertical_landing, {"vertical": "cleaning"}, name="vertical_cleaning"),
    path("landscaping/", vertical_landing, {"vertical": "landscaping"}, name="vertical_landscaping"),

    # Public booking page (no auth)
    path("book/<str:token>/", public_booking, name="public_booking"),

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
    path("settings/service-pricing/", include("pricing.urls")),
    path("subscription/", include("subscription.urls")),
    path("webhooks/stripe/", include("subscription.webhook_urls")),
    path("financials/", include(("financials.urls", "financials"), namespace="financials")),
    path("estimator/", include("property_estimator.urls")),
    path("api/messages/", include("messaging.urls")),
    path("fertilization/", include(("fertilization.urls", "fertilization"), namespace="fertilization")),
    path("pricebook/", include(("pricebook.urls", "pricebook"), namespace="pricebook")),
    path("equipment/", include(("equipment.urls", "equipment"), namespace="equipment")),
    path("agreements/", include(("service_agreements.urls", "service_agreements"), namespace="service_agreements")),
    path("checklists/", include(("checklists.urls", "checklists"), namespace="checklists")),
    path("inspections/", include(("inspections.urls", "inspections"), namespace="inspections")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
