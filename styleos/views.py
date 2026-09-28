
def _capsule(items, limit=10):
    """Backward-compatible quick capsule helper for existing tests/integrations."""
    available=[x for x in items if x.status=="clean" and x.category!="accessory"]
    chosen=[]; categories=set()
    for item in sorted(available, key=lambda x: (-x.wear_count, x.name)):
        if len(chosen)>=limit:
            break
        if item.category not in categories or len(chosen)>=max(1,limit-3):
            chosen.append(item)
            categories.add(item.category)
    return chosen
"""WardrobeOS Style Intelligence command center."""
from datetime import date

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts_app.models import resolve_location
from ai.matching import recommend
from ai.providers import complete_text
from config.scoping import scoped_items, scoped_outfits, scoped_plans, scoped_trips
from weather.service import get_weather, summarize

from .engine import (
    capsule_for_trip, remix_candidates, seven_day_context,
    style_genome, wardrobe_gaps, wardrobe_roi,
)
from .forms import StyleCoachForm


def _weather(user):
    place = resolve_location(user)
    try:
        data = summarize(get_weather(place["lat"], place["lon"]))
        data["city"] = place["city"]
        return data
    except Exception:
        return {"temp": None, "kind": None, "label": "Weather offline",
                "emoji": "🌤️", "city": place["city"]}


def _daily(user):
    place = resolve_location(user)
    try:
        raw = get_weather(place["lat"], place["lon"]).get("daily", {})
        dates = raw.get("time", [])
        codes = raw.get("weather_code", [])
        mins = raw.get("temperature_2m_min", [])
        maxs = raw.get("temperature_2m_max", [])
        return [{
            "date": d,
            "code": codes[i] if i < len(codes) else None,
            "min": mins[i] if i < len(mins) else None,
            "max": maxs[i] if i < len(maxs) else None,
        } for i, d in enumerate(dates[:7])]
    except Exception:
        return []


def command_center(request):
    items_qs = scoped_items(request.user)
    outfits_qs = scoped_outfits(request.user)
    plans_qs = scoped_plans(request.user)
    items = list(items_qs)
    outfits = list(outfits_qs[:40])
    wx = _weather(request.user)

    worn = [x for x in items if x.wear_count]
    clean = [x for x in items if x.status == "clean"]
    categories = {x.category for x in items}
    families = {x.color_family for x in items if x.color_family}
    pulse = round(
        (len(worn) / (len(items) or 1)) * 30
        + (len(clean) / (len(items) or 1)) * 25
        + min(25, len(categories) * 2.5)
        + min(20, len(families) * 3)
    )
    pulse = max(0, min(100, pulse))

    genome = style_genome(items, outfits)
    roi = wardrobe_roi(items)
    gaps = wardrobe_gaps(items)
    ootd = (recommend(items_qs, "casual", wx.get("temp") or 25, wx.get("kind")) or [None])[0]

    plans = list(
        plans_qs.filter(date__gte=date.today()).order_by("date")[:7]
    )
    daily = seven_day_context(plans, _daily(request.user))
    trips = list(scoped_trips(request.user).order_by("start_date")[:3])
    trip = trips[0] if trips else None
    trip_capsule = capsule_for_trip(items, trip) if trip else []
    capsule = _capsule(items, 10)

    return render(request, "styleos/command_center.html", {
        "pulse": pulse,
        "pulse_label": "In rhythm" if pulse >= 75 else "Finding its rhythm" if pulse >= 50 else "Needs attention",
        "pulse_text": "A combined signal from use, care, category coverage and palette diversity.",
        "pulse_metrics": [
            ("Utilization", round(len(worn) / (len(items) or 1) * 100), "Pieces with real wear history"),
            ("Care", round(len(clean) / (len(items) or 1) * 100), "Ready-to-wear inventory"),
            ("Coverage", min(100, len(categories) * 8), "Category breadth"),
            ("Palette", min(100, len(families) * 15), "Colour-family diversity"),
        ],
        "items_count": len(items),
        "worn_count": len(worn),
        "never_count": len([x for x in items if not x.wear_count]),
        "laundry_count": len([x for x in items if x.status in ("worn", "laundry")]),
        "ootd": ootd,
        "weather": wx,
        "genome": genome,
        "roi": roi,
        "gaps": gaps,
        "daily": daily,
        "trip_capsule": trip_capsule,
        "capsule": capsule,
        "trip": trip,
        "recent_outfits": outfits[:6],
        "coach_form": StyleCoachForm(),
        "coach_answer": request.session.pop("style_coach_answer", ""),
        "remix_results": request.session.pop("style_remix", []),
    })


@require_POST
def style_coach(request):
    form = StyleCoachForm(request.POST)
    if not form.is_valid():
        return redirect("style_command_center")
    items = list(scoped_items(request.user))
    outfits = list(scoped_outfits(request.user)[:20])
    genome = style_genome(items, outfits)
    facts = [{
        "name": x.name, "category": x.category, "color": x.color,
        "formality": x.formality, "wears": x.wear_count, "status": x.status,
    } for x in items[:80]]
    prompt = (
        "You are the WardrobeOS personal style coach. Answer using ONLY the "
        "supplied wardrobe facts. Do not invent clothing. If information is "
        "missing, say so. Give practical, concise advice. "
        f"STYLE GENOME: {genome}. WARDROBE: {facts}. "
        f"USER QUESTION: {form.cleaned_data['question']}"
    )
    result = complete_text(
        prompt,
        system="Be an honest wardrobe coach. Prefer concrete combinations and explain why.",
        max_tokens=700,
        temperature=0.4,
    )
    request.session["style_coach_answer"] = (
        result.text if result.ok
        else "Coach unavailable right now. Your deterministic Style Intelligence panels remain available."
    )
    return redirect("style_command_center")


@require_POST
def remix(request, pk):
    outfit = get_object_or_404(scoped_outfits(request.user), pk=pk)
    candidates = remix_candidates(scoped_items(request.user), outfit)
    request.session["style_remix"] = [
        {"replace": x["replace"].name, "with": x["with"].name, "reason": x["reason"]}
        for x in candidates
    ]
    return redirect("style_command_center")
