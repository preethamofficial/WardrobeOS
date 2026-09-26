"""Weather service: Open-Meteo (free, keyless) - forecast, geocoding, helpers."""
import time

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_CACHE = {}
CACHE_TTL = 600  # 10 minutes


def _cached(key, fn):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    value = fn()
    _CACHE[key] = (now, value)
    return value


def geocode(city):
    """City name -> {lat, lon, name, country} via Open-Meteo geocoding (free)."""
    def fetch():
        r = requests.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "en", "format": "json"}, timeout=8)
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            return None
        top = results[0]
        return {"lat": top["latitude"], "lon": top["longitude"],
                "name": top.get("name", city), "country": top.get("country", "")}
    try:
        return _cached(f"geo:{str(city).lower()}", fetch)
    except Exception:
        return None


def get_weather(lat=12.9716, lon=77.5946):
    def fetch():
        params = {"latitude": lat, "longitude": lon,
                  "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                  "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                  "forecast_days": 14, "timezone": "auto"}
        r = requests.get(FORECAST_URL, params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    return _cached(f"wx:{lat}:{lon}", fetch)


_WMO = [
    ((0, 0), ("Clear sky", "☀️", "clear")), ((1, 3), ("Partly cloudy", "⛅", "cloudy")),
    ((45, 48), ("Foggy", "🌫️", "fog")), ((51, 57), ("Drizzle", "🌦️", "rain")),
    ((61, 67), ("Rain", "🌧️", "rain")), ((71, 77), ("Snow", "❄️", "snow")),
    ((80, 82), ("Showers", "🌦️", "rain")), ((85, 86), ("Snow showers", "🌨️", "snow")),
    ((95, 99), ("Thunderstorm", "⛈️", "storm")),
]


def describe_code(code):
    for (lo, hi), info in _WMO:
        if code is not None and lo <= code <= hi:
            return info
    return ("Unknown", "🌡️", "unknown")


def summarize(data):
    """Raw Open-Meteo payload -> tidy dict the UI and engine can use."""
    current = (data or {}).get("current", {})
    daily = (data or {}).get("daily", {})
    code = current.get("weather_code", 0)
    label, emoji, kind = describe_code(code)
    temp = current.get("temperature_2m")
    probs = daily.get("precipitation_probability_max") or [None]
    return {"temp": temp, "feels": current.get("apparent_temperature", temp),
            "humidity": current.get("relative_humidity_2m"), "wind": current.get("wind_speed_10m"),
            "code": code, "label": label, "emoji": emoji, "kind": kind,
            "rainy": kind in ("rain", "storm"), "snowy": kind == "snow",
            "hot": (temp or 0) >= 30, "cold": (temp or 0) <= 12,
            "precip_prob": probs[0] if probs else None,
            "days": [{"date": d, "code": c, "min": mn, "max": mx}
                     for d, c, mn, mx in zip(daily.get("time", []) or [],
                                             daily.get("weather_code") or [],
                                             daily.get("temperature_2m_min") or [],
                                             daily.get("temperature_2m_max") or [])]}
