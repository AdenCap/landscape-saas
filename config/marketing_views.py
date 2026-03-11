from django.shortcuts import render, redirect
from django.http import Http404, HttpResponse
from django.conf import settings


def _marketing_redirect_for_auth(request):
    user = request.user
    if not user.is_authenticated:
        return None
    role = getattr(user, "role", None)
    if role == "crew":
        return redirect("/jobs/crew/")
    return redirect("/dashboard/")


def _marketing_context():
    return {
        "pricing": {
            "solo_price": getattr(settings, "PLATFORM_SOLO_PRICE", "29.99"),
            "pro_price": getattr(settings, "PLATFORM_PRO_PRICE", "99.99"),
        },
        "ga_measurement_id": getattr(settings, "GA4_MEASUREMENT_ID", ""),
    }


def marketing_home(request):
    """
    Public landing page for the FieldLgx platform.

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
        "title": "Dashboard Command Center",
        "subtitle": "Run the day from one operational control surface.",
        "seo_description": "FieldLgx Dashboard centralizes schedule, revenue, invoices, and team activity for landscaping operators.",
        "bullets": ["Today's schedule and blockers", "Revenue and collections at a glance", "Live team activity stream"],
        "roles": {
            "Owner": "See today's performance and decide fast with KPI-level visibility.",
            "Dispatcher": "Prioritize issues and keep schedule pressure under control.",
            "Crew Lead": "Get clear execution context without hunting for information."
        }
    },
    "jobs": {
        "title": "Job Management",
        "subtitle": "Track work from scheduled to completed with zero guesswork.",
        "bullets": ["Status-first workflow", "Fast job editing", "Clear ownership across crews"],
    },
    "calendar": {
        "title": "Scheduling Calendar",
        "subtitle": "Drag, drop, and rebalance your workload in seconds.",
        "bullets": ["Day/week/month views", "Reschedule with confidence", "Crew-aware planning"],
    },
    "daily-routes": {
        "title": "Daily Routes",
        "subtitle": "Turn schedules into efficient route execution.",
        "bullets": ["Route clarity for crews", "Reduce travel waste", "Faster first-job starts"],
    },
    "clients": {
        "title": "Client CRM",
        "subtitle": "Keep every customer record, property, and conversation in sync.",
        "bullets": ["Unified customer profiles", "Service + invoice history", "Quick lookup from field and office"],
    },
    "messaging": {
        "title": "Client Messaging",
        "subtitle": "Centralized communication without app-switching.",
        "bullets": ["Inbox-style message flow", "Context tied to jobs", "Faster response operations"],
    },
    "estimator": {
        "title": "Estimator Tools",
        "subtitle": "Quote faster with structured estimating workflows.",
        "bullets": ["Guided estimate creation", "Service-level pricing clarity", "Smoother quote-to-job handoff"],
    },
    "invoices": {
        "title": "Invoice Builder",
        "subtitle": "Professional invoices that speed up payment.",
        "bullets": ["Clean line-item editing", "Payment-state visibility", "Faster closeout after completion"],
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
        "subheadline": "Schedule crews, optimize routes, send invoices, and grow your lawn care business.",
        "seo_title": "FieldLgx for Landscaping — Crew Scheduling & Route Software",
        "seo_description": "FieldLgx helps landscaping and lawn care businesses schedule crews, plan routes, send invoices, and manage clients from one platform.",
        "pain_points": [
            ("Route inefficiency", "Optimize daily routes so crews spend more time mowing and less time driving."),
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
        "/", "/features/", "/pricing/", "/automation/", "/terms/", "/privacy/",
    ] + [f"/features/{slug}/" for slug in FEATURE_PAGES.keys()] + [f"/{v}/" for v in VERTICAL_PAGES.keys()]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in urls:
        xml.append(f"<url><loc>{base}{path}</loc></url>")
    xml.append("</urlset>")
    return HttpResponse("".join(xml), content_type="application/xml")
