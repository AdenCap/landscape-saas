from django.shortcuts import render, redirect


def marketing_home(request):
    """
    Public landing page for the Field Ops platform.

    - Anonymous visitors see the marketing site with features and pricing overview.
    - Authenticated users are redirected into the app so `/` still behaves like
      "Dashboard" from their perspective.
    """
    user = request.user
    if user.is_authenticated:
        role = getattr(user, "role", None)
        if role == "crew":
            return redirect("/jobs/crew/")
        # Owners and any other staff-style roles go to the main dashboard
        # Use absolute path to avoid redirect loops
        return redirect("/dashboard/")

    return render(request, "marketing/landing.html")

