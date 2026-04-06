"""
Business timezone utilities.
Use business_today(business) instead of timezone.localdate() or timezone.now().date()
to get the correct "today" in the business's configured timezone.
"""
from datetime import datetime
from django.utils import timezone


def business_today(business=None):
    """Get today's date in the business's timezone (not server UTC).
    Falls back to Django's localdate() if no business or timezone is set."""
    if business and hasattr(business, 'timezone') and business.timezone:
        try:
            import zoneinfo
            biz_tz = zoneinfo.ZoneInfo(business.timezone)
            return datetime.now(biz_tz).date()
        except Exception:
            pass
    return timezone.localdate()
