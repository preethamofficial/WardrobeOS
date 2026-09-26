"""Global template context helpers."""
import os

from django.conf import settings

from accounts_app.models import resolve_location
from weather.service import get_weather, summarize


def weather(request):
    """Live weather for the *viewer's* city.

    This used to read DEFAULT_LATITUDE / DEFAULT_CITY from the environment, so
    every visitor of a hosted deployment saw Bengaluru. It now resolves the
    location per request: the signed-in user's saved city first, environment
    defaults only as fallback.
    """
    user = getattr(request, "user", None)
    place = resolve_location(user)
    try:
        data = summarize(get_weather(place["lat"], place["lon"]))
        data["city"] = place["city"]
    except Exception:
        data = {"emoji": "🌡️", "label": "weather offline", "city": place["city"],
                "temp": None, "kind": None, "rainy": False, "hot": False, "cold": False}
    return {"live_weather": data, "location": place}


def auth_flags(request):
    """Expose which auth options are active to templates (e.g. Google button)."""
    providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}) or {}
    return {"google_enabled": bool(providers.get("google"))}