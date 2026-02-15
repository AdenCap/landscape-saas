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
admin.site.index_title = "Manage your business, employees, and customers"

from config.platform_views import platform_home, platform_enter, platform_exit

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("accounts.auth_urls")),

    # Platform admin (superuser only): list businesses and enter any dashboard
    path('platform/', platform_home, name='platform_home'),
    path('platform/enter/<int:business_id>/', platform_enter, name='platform_enter'),
    path('platform/exit/', platform_exit, name='platform_exit'),

    # Homepage = Dashboard
    path('', include('dashboard.urls')),

    # App routes
    path("dashboard", include("dashboard.urls")),  # owner dashboard becomes homepage
    path("billing/", include(("billing.urls", "billing"), namespace="billing")),
    path("clients/", include("customers.urls")),
    path("employees/", include("accounts.urls")),
    path("crews/", include("jobs.crew_urls")),
    path("jobs/", include("jobs.urls")),
    path("time/", include("time_tracking.urls")),
    path("settings/", include("businesses.urls")),
    path("quickbooks/", include(("quickbooks.urls", "quickbooks"), namespace="quickbooks")),
    path("financials/", include(("financials.urls", "financials"), namespace="financials")),
    path("estimator/", include("property_estimator.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
