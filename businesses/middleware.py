from zoneinfo import ZoneInfo

from django.utils import timezone


class TimezoneMiddleware:
    """Activate the logged-in user's business timezone for every request.

    Once activated, all Django template date filters (|date, |time) and
    timezone.localtime() / timezone.localdate() calls automatically use
    the business's timezone instead of UTC.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = None
        if hasattr(request, "user") and request.user.is_authenticated:
            try:
                tz_name = request.user.business.timezone
            except Exception:
                pass

        if tz_name:
            timezone.activate(ZoneInfo(tz_name))
        else:
            timezone.deactivate()

        response = self.get_response(request)
        return response
