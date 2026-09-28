"""Global template context helpers."""
from django.conf import settings
from django.core.cache import cache

from accounts_app.models import resolve_location
from weather.service import get_weather, summarize


def weather(request):
    """Cached live weather for the viewer's saved city."""
    user = getattr(request, "user", None)
    place = resolve_location(user)
    key = f"wardrobeos:weather:{place['lat']:.4f}:{place['lon']:.4f}"
    data = cache.get(key)
    if data is None:
        try:
            data = summarize(get_weather(place["lat"], place["lon"]))
            data["city"] = place["city"]
        except Exception:
            data = {
                "emoji": "🌡️", "label": "weather offline", "city": place["city"],
                "temp": None, "kind": None, "rainy": False, "hot": False,
                "cold": False, "precip_prob": None,
            }
        cache.set(key, data, 600)
    return {"live_weather": data, "location": place}


def auth_flags(request):
    """Expose which auth options are active to templates."""
    providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {}) or {}
    return {"google_enabled": bool(providers.get("google"))}
