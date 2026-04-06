"""
Business timezone utilities.
Use business_today(business) instead of timezone.localdate() or timezone.now().date()
to get the correct "today" in the business's configured timezone.
"""
import zoneinfo
from datetime import datetime
from django.utils import timezone

# Hard-coded default — must match settings.TIME_ZONE
_DEFAULT_TZ = 'America/New_York'


def _get_tz_name(business=None):
    """Resolve timezone name from business or fall back to default."""
    if business and hasattr(business, 'timezone') and business.timezone:
        return business.timezone
    return _DEFAULT_TZ


def business_today(business=None):
    """Get today's date in the business's configured timezone.
    Falls back to America/New_York if no business timezone is set."""
    tz_name = _get_tz_name(business)
    try:
        biz_tz = zoneinfo.ZoneInfo(tz_name)
        return datetime.now(biz_tz).date()
    except Exception:
        return timezone.localdate()


def business_now(business=None):
    """Get the current datetime in the business's timezone."""
    tz_name = _get_tz_name(business)
    try:
        biz_tz = zoneinfo.ZoneInfo(tz_name)
        return datetime.now(biz_tz)
    except Exception:
        return timezone.localtime()
