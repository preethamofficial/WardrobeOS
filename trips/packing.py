"""Smart packing list generator.

Combines trip length + destination forecast (Open-Meteo, free) + your actual
clean wardrobe items into a checkable packing list stored on the Trip.
"""
from weather.service import describe_code, get_weather

_WARDROBE_HINTS = ["goa", "beach", "bali", "maldives", "miami", "hawaii", "santorini", "cancun"]


def forecast_window(lat, lon, start_iso, end_iso):
    """Daily forecasts (date, code, min, max) clipped to the trip window."""
    try:
        daily = get_weather(lat, lon).get("daily", {})
        times = daily.get("time", []) or []
        out = []
        for i, d in enumerate(times):
            if start_iso <= d <= end_iso:
                codes = daily.get("weather_code") or []
                mins = daily.get("temperature_2m_min") or []
                maxs = daily.get("temperature_2m_max") or []
                out.append({"date": d,
                            "code": codes[i] if i < len(codes) else None,
                            "min": mins[i] if i < len(mins) else None,
                            "max": maxs[i] if i < len(maxs) else None})
        return out
    except Exception:
        return []


def _entry(name, qty, kind="essential"):
    return {"name": name, "qty": qty, "type": kind, "packed": False}


def _from_wardrobe(items, categories, label):
    for it in items:
        if it.category in categories and it.status == "clean":
            return _entry(f"{label}: {it.name}", 1, "wardrobe")
    return None


def build(trip, items):
    """Return the packing list for a trip (also stored on trip.packing)."""
    nights = max(1, trip.nights)
    pack = [
        _entry("Underwear", nights + 1), _entry("Socks", nights + 1),
        _entry("T-shirts / tops", nights + 1), _entry("Pants / bottoms", max(2, nights // 2 + 1)),
        _entry("Toiletry kit", 1), _entry("Phone charger", 1), _entry("ID / wallet / keys", 1),
    ]
    days = []
    if trip.lat is not None and trip.lon is not None:
        days = forecast_window(trip.lat, trip.lon, trip.start_date.isoformat(), trip.end_date.isoformat())
    mins = [d["min"] for d in days if d["min"] is not None]
    maxs = [d["max"] for d in days if d["max"] is not None]
    wet = [d for d in days if describe_code(d["code"])[2] in ("rain", "storm", "snow")]
    if wet:
        pack.append(_entry("Rain jacket / umbrella", 1, "weather"))
    if any(m <= 14 for m in mins):
        pack += [_entry("Warm sweater / fleece", 1, "weather"), _entry("Closed warm shoes", 1, "weather")]
    if any(m >= 28 for m in maxs):
        pack += [_entry("Shorts", max(2, nights // 2), "weather"), _entry("Sunscreen + sunglasses", 1, "weather")]
    if any(k in trip.destination.lower() for k in _WARDROBE_HINTS):
        pack += [_entry("Swimwear", 1, "beach"), _entry("Flip flops", 1, "beach")]
    for categories, label in ((("jacket", "hoodie"), "Layer"), (("shirt", "tshirt"), "Top"),
                              (("pant", "jeans"), "Bottom"), (("shoes",), "Footwear")):
        pick = _from_wardrobe(items, categories, label)
        if pick:
            pack.append(pick)
    return pack