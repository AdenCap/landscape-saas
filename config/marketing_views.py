from django.shortcuts import render, redirect


def _marketing_redirect_for_auth(request):
    user = request.user
    if not user.is_authenticated:
        return None
    role = getattr(user, "role", None)
    if role == "crew":
        return redirect("/jobs/crew/")
    return redirect("/dashboard/")


def marketing_home(request):
    """
    Public landing page for the Field Ops platform.

    - Anonymous visitors see the marketing site with features and pricing overview.
    - Authenticated users are redirected into the app so `/` still behaves like
      "Dashboard" from their perspective.
    """
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/landing.html")


def marketing_features(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/features.html")


def marketing_automation(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/automation.html")


def marketing_pricing(request):
    r = _marketing_redirect_for_auth(request)
    if r:
        return r
    return render(request, "marketing/pricing.html")


def terms_of_service(request):
    """Terms of Service page."""
    return render(request, "marketing/terms.html")


def privacy_policy(request):
    """Privacy Policy page."""
    return render(request, "marketing/privacy.html")
