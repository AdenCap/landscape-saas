from django.shortcuts import render, redirect
from django.http import Http404, HttpResponse
from django.conf import settings


def _marketing_redirect_for_auth(request):
    if request.GET.get("preview_marketing") == "1":
        return None
    user = request.user
    if not user.is_authenticated:
        return None
    role = getattr(user, "role", None)
    if role == "crew":
        return redirect("/jobs/crew/")
    return redirect("/dashboard/")


def _marketing_context():
    return {
        "app_url": getattr(settings, "APP_BASE_URL", "https://app.fieldlgx.com").rstrip("/"),
        "public_site_url": getattr(settings, "PUBLIC_SITE_URL", "https://fieldlgx.com").rstrip("/"),
        "pricing": {
            "solo_price": getattr(settings, "PLATFORM_SOLO_PRICE", "29.99"),
            "pro_price": getattr(settings, "PLATFORM_PRO_PRICE", "99.99"),
        },
        "ga_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
    }


def marketing_home(request):
    """
    Public landing page for the FIELDLGX platform.

    - Anonymous visitors see the marketing site with features and pricing overview.
    - Authenticated users are redirected into the app so `/` still behaves like
      "Dashboard" from their perspective.
    """
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/landing.html", _marketing_context())


FEATURE_PAGES = {
    "dashboard": {
        "title": "Field Command Dashboard",
        "subtitle": "Run the day from one operational control surface.",
        "seo_description": "FIELDLGX Field Command gives lawn care and landscaping companies one dashboard for schedules, unassigned jobs, crew activity, billing status, invoices, and daily operations.",
        "bullets": ["Today's schedule and blockers", "Revenue and collections at a glance", "Crew, job, and billing visibility"],
        "roles": {
            "Owner": "See today's performance and decide fast with KPI-level visibility.",
            "Dispatcher": "Prioritize issues and keep schedule pressure under control.",
            "Crew Lead": "Get clear execution context without hunting for information."
        }
    },
    "jobs": {
        "title": "Lawn Care Job Management",
        "subtitle": "Track work from scheduled to completed with zero guesswork.",
        "seo_description": "Manage lawn care and landscaping jobs with FIELDLGX. Track scheduled, completed, skipped, recurring, and billable work with notes, photos, line items, crews, and job history.",
        "bullets": ["Status-first job workflow", "Fast job editing from the field", "Clear ownership across crews"],
    },
    "calendar": {
        "title": "Lawn Care Scheduling Calendar",
        "subtitle": "Drag, drop, and rebalance your workload in seconds.",
        "seo_description": "FIELDLGX scheduling software helps lawn care and landscaping companies manage day, week, month, and schedule views for recurring jobs, multi-day work, crews, and route planning.",
        "bullets": ["Day, week, month, and schedule views", "Recurring job scheduling", "Crew-aware calendar planning"],
    },
    "daily-routes": {
        "title": "Daily Route Planning",
        "subtitle": "Turn schedules into efficient route execution.",
        "seo_description": "Plan daily routes for lawn care and landscaping crews with FIELDLGX. Keep property details, maps, crew notes, job items, and completion status connected to the schedule.",
        "bullets": ["Route clarity for crews", "Map and property context", "Faster first-job starts"],
    },
    "clients": {
        "title": "Landscaping Client CRM",
        "subtitle": "Keep every customer record, property, and conversation in sync.",
        "seo_description": "FIELDLGX landscaping CRM keeps customer profiles, property addresses, crew-visible notes, internal notes, billing preferences, job history, estimates, and invoices in one place.",
        "bullets": ["Unified customer profiles", "Service and invoice history", "Quick lookup from field and office"],
    },
    "messaging": {
        "title": "Client Messaging",
        "subtitle": "Centralized communication without app-switching.",
        "bullets": ["Inbox-style message flow", "Context tied to jobs", "Faster response operations"],
    },
    "estimator": {
        "title": "Landscape Estimate Builder",
        "subtitle": "Quote faster with structured estimating workflows.",
        "seo_description": "Create professional landscaping estimates and lawn care quotes with FIELDLGX. Build line items, preview customer-facing documents, send follow-ups, and convert approved estimates into jobs.",
        "bullets": ["Guided estimate creation", "Service-level pricing clarity", "Smoother quote-to-job handoff"],
    },
    "invoices": {
        "title": "Lawn Care Invoice Builder",
        "subtitle": "Professional invoices that speed up payment.",
        "seo_description": "FIELDLGX lawn care invoicing software helps landscaping companies edit line items, add descriptions, track payment status, send reminders, manage monthly invoice batches, and collect payments.",
        "bullets": ["Clean line-item editing", "Payment-state visibility", "Monthly and batch invoice workflows"],
    },
    "estimates": {
        "title": "Estimates",
        "subtitle": "Move prospects from quote to approved work quickly.",
        "bullets": ["Structured estimate pipeline", "Follow-up visibility", "Owner-level control on send cadence"],
    },
    "employee-management": {
        "title": "Employee Management",
        "subtitle": "Manage team roles, assignments, and accountability.",
        "bullets": ["Crew and user administration", "Operational visibility", "Reliable role-based access"],
    },
    "financials": {
        "title": "Financials & Analytics",
        "subtitle": "Track performance, margins, and trends with confidence.",
        "seo_description": "FIELDLGX financial dashboards help lawn care and landscaping owners track revenue, outstanding invoices, completed work, collections, and business health from one operations platform.",
        "bullets": ["Revenue trend visibility", "Collection performance", "Business health metrics"],
    },
}


def marketing_features(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    ctx = _marketing_context()
    ctx.update({"feature_pages": FEATURE_PAGES})
    return render(request, "marketing/features.html", ctx)


def marketing_feature_detail(request, slug):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    feature = FEATURE_PAGES.get(slug)
    if not feature:
        raise Http404("Feature page not found")
    if "roles" not in feature:
        feature["roles"] = {
            "Owner": "Get strategic visibility and control over daily operations.",
            "Dispatcher": "Keep assignments, timing, and customer communication aligned.",
            "Crew Lead": "Execute work with clear context and fewer blockers."
        }
    if "seo_description" not in feature:
        feature["seo_description"] = f"{feature['title']} for landscaping teams: {feature['subtitle']}"
    ctx = _marketing_context()
    ctx.update({"feature": feature, "slug": slug})
    return render(request, "marketing/feature_detail.html", ctx)


def marketing_automation(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/automation.html")


def marketing_pricing(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/pricing.html", _marketing_context())


def terms_of_service(request):
    """Terms of Service page."""
    return render(request, "marketing/terms.html")


def privacy_policy(request):
    """Privacy Policy page."""
    return render(request, "marketing/privacy.html")


VERTICAL_PAGES = {
    "landscaping": {
        "type_label": "Landscaping",
        "headline": "The operating system for landscaping businesses",
        "subheadline": "Schedule crews, plan routes, manage recurring lawn services, send estimates and invoices, collect payments, and grow your lawn care business.",
        "seo_title": "Lawn Care & Landscaping Software for Scheduling, CRM & Invoicing | FIELDLGX",
        "seo_description": "FIELDLGX helps landscaping and lawn care businesses schedule crews, plan routes, manage recurring jobs, create estimates, send invoices, collect payments, and manage clients from one platform.",
        "pain_points": [
            ("Route inefficiency", "Plan cleaner daily routes so crews spend more time mowing and less time driving."),
            ("Crew communication gaps", "Everyone sees the same schedule. Updates happen in real-time, not via group text."),
            ("Seasonal revenue dips", "Sell fertilization and maintenance plans to keep cash flowing year-round."),
        ],
        "features": [
            ("Route Optimization", "Plan efficient daily routes for every crew with map-based planning."),
            ("Crew Scheduling", "Assign jobs to crews and see workload balance across your team."),
            ("Property Estimator", "Measure properties and generate accurate quotes with satellite imagery."),
            ("Fertilization Tracking", "Track application schedules, products, and compliance for lawn treatments."),
        ],
    },
}


def vertical_landing(request, vertical):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    page = VERTICAL_PAGES.get(vertical)
    if not page:
        raise Http404("Vertical page not found")
    ctx = _marketing_context()
    ctx.update({"page": page, "vertical": vertical})
    return render(request, "marketing/vertical_landing.html", ctx)


def robots_txt(request):
    base = getattr(settings, "CANONICAL_BASE_URL", "https://fieldlgx.com").rstrip("/")
    body = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    return HttpResponse(body, content_type="text/plain")


def sitemap_xml(request):
    base = getattr(settings, "CANONICAL_BASE_URL", "https://fieldlgx.com").rstrip("/")
    urls = [
        ("/", "daily", "1.0"),
        ("/features/", "weekly", "0.9"),
        ("/pricing/", "weekly", "0.9"),
        ("/automation/", "weekly", "0.8"),
        ("/terms/", "monthly", "0.3"),
        ("/privacy/", "monthly", "0.3"),
    ]
    urls += [(f"/features/{slug}/", "weekly", "0.75") for slug in FEATURE_PAGES.keys()]
    urls += [(f"/{v}/", "weekly", "0.85") for v in VERTICAL_PAGES.keys()]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, changefreq, priority in urls:
        xml.append(f"<url><loc>{base}{path}</loc><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>")
    xml.append("</urlset>")
    return HttpResponse("".join(xml), content_type="application/xml")
