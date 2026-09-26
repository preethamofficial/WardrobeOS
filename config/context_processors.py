"""Global template context helpers."""
import os

from django.conf import settings

from weather.service import get_weather, summarize


def weather(request):
    try:
        data = summarize(get_weather(float(os.getenv("DEFAULT_LATITUDE", "12.9716")),
                                     float(os.getenv("DEFAULT_LONGITUDE", "77.5946"))))
        data["city"] = os.getenv("DEFAULT_CITY", "Bengaluru")
    except Exception:
        data = {"emoji": "🌡️", "label": "weather offline", "city": os.getenv("DEFAULT_CITY", ""),
                "temp": None, "kind": None, "rainy": False, "hot": False, "cold": False}
    return {"live_weather": data}


def auth_flags(request):
    """Expose which auth options are active to templates (e.g. Google button)."""
    providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}) or {}
    return {"google_enabled": bool(providers.get("google"))}