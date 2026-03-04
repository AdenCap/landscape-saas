"""Weather forecast integration using Open-Meteo API (free, no API key required)."""
import logging
from datetime import date

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# WMO Weather interpretation codes → (label, lucide icon name)
WEATHER_ICONS = {
    0: ("Clear sky", "sun"),
    1: ("Mostly clear", "sun"),
    2: ("Partly cloudy", "cloud-sun"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "cloud-fog"),
    48: ("Rime fog", "cloud-fog"),
    51: ("Light drizzle", "cloud-drizzle"),
    53: ("Drizzle", "cloud-drizzle"),
    55: ("Dense drizzle", "cloud-drizzle"),
    56: ("Freezing drizzle", "cloud-drizzle"),
    57: ("Freezing drizzle", "cloud-drizzle"),
    61: ("Light rain", "cloud-rain"),
    63: ("Rain", "cloud-rain"),
    65: ("Heavy rain", "cloud-rain-wind"),
    66: ("Freezing rain", "cloud-rain"),
    67: ("Heavy freezing rain", "cloud-rain-wind"),
    71: ("Light snow", "snowflake"),
    73: ("Snow", "snowflake"),
    75: ("Heavy snow", "snowflake"),
    77: ("Snow grains", "snowflake"),
    80: ("Light showers", "cloud-rain"),
    81: ("Showers", "cloud-rain"),
    82: ("Heavy showers", "cloud-rain-wind"),
    85: ("Snow showers", "snowflake"),
    86: ("Heavy snow showers", "snowflake"),
    95: ("Thunderstorm", "cloud-lightning"),
    96: ("Thunderstorm with hail", "cloud-lightning"),
    99: ("Thunderstorm with hail", "cloud-lightning"),
}


def get_forecast(lat, lon, days=7):
    """Fetch a multi-day weather forecast from Open-Meteo.

    Returns a list of dicts:
        [{"date": "2026-03-04", "high": 72, "low": 55, "precip": 0.1,
          "label": "Partly cloudy", "icon": "cloud-sun", "code": 2}, ...]

    Results are cached for 2 hours.
    """
    cache_key = f"weather:{lat:.2f}:{lon:.2f}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"
        f"&temperature_unit=fahrenheit"
        f"&precipitation_unit=inch"
        f"&timezone=auto"
        f"&forecast_days={days}"
    )
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("weather_fetch_failed lat=%s lon=%s error=%s", lat, lon, exc)
        return []

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])
    codes = daily.get("weathercode", [])

    result = []
    for i, d in enumerate(dates):
        code = codes[i] if i < len(codes) else 0
        label, icon = WEATHER_ICONS.get(code, ("Unknown", "cloud"))
        result.append({
            "date": d,
            "high": round(highs[i]) if i < len(highs) else None,
            "low": round(lows[i]) if i < len(lows) else None,
            "precip": round(precips[i], 2) if i < len(precips) else 0,
            "label": label,
            "icon": icon,
            "code": code,
        })

    cache.set(cache_key, result, 7200)  # 2 hours
    return result


def get_business_location(business):
    """Get lat/lon for a business by checking its customer properties.

    Returns (lat, lon) tuple or None.
    Caches the result permanently (business location rarely changes).
    """
    cache_key = f"biz_location:{business.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached if cached != "none" else None

    from customers.models import Property
    prop = (
        Property.objects
        .filter(customer__business=business, latitude__isnull=False, longitude__isnull=False)
        .exclude(latitude=0, longitude=0)
        .values_list("latitude", "longitude")
        .first()
    )
    if prop:
        result = (float(prop[0]), float(prop[1]))
        cache.set(cache_key, result, 86400 * 30)  # 30 days
        return result

    cache.set(cache_key, "none", 3600)  # re-check in 1 hour
    return None
