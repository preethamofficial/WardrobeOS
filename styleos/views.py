"""WardrobeOS Style Intelligence: a fast, explainable layer over existing data.

This app deliberately has no new database tables. It derives its signals from
the existing wardrobe, outfit, planner and laundry data so the feature is
instant to deploy and cannot create another source of truth.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from ai.colors import normalize_palette
from ai.matching import recommend
from config.scoping import scoped_items, scoped_outfits, scoped_plans
from weather.service import get_weather, summarize


def _weather():
    try:
        return summarize(get_weather())
    except Exception:
        return {
            "temp": 25, "kind": None, "label": "Weather unavailable",
            "emoji": "🌤️", "rainy": False, "hot": False, "cold": False,
            "precip_prob": None,
        }


def _clamp(value):
    return max(0, min(100, int(round(value))))


def _capsule(items, limit=10):
    """Build a deterministic capsule with category coverage and color variety."""
    available = [x for x in items if x.status == "clean" and x.category != "accessory"]
    if not available:
        return []

    # Prioritise useful pieces without simply returning the most-worn items.
    category_priority = {
        "shirt": 8, "tshirt": 7, "pant": 8, "jeans": 8, "shorts": 5,
        "dress": 9, "skirt": 7, "jacket": 7, "hoodie": 6, "sweater": 6,
        "shoes": 9, "accessory": 3, "other": 2,
    }
    chosen = []
    seen_categories = set()
    seen_families = set()

    def score(item):
        family = (item.color_family or "").lower()
        category = item.category
        freshness = 1 if item.last_worn is None else max(
            0, min(6, (timezone.now() - item.last_worn).days // 14)
        )
        diversity = 7 if family and family not in seen_families else 0
        coverage = 10 if category not in seen_categories else 0
        return (
            coverage + diversity + category_priority.get(category, 2)
            + min(item.wear_count, 6) + freshness
        )

    remaining = available[:]
    while remaining and len(chosen) < limit:
        remaining.sort(key=score, reverse=True)
        pick = remaining.pop(0)
        chosen.append(pick)
        seen_categories.add(pick.category)
        if pick.color_family:
            seen_families.add(pick.color_family.lower())

    return chosen


def _missions(items, outfits):
    now = timezone.now()
    missions = []
    never = [x for x in items if x.wear_count == 0 and x.status == "clean"]
    idle = [
        x for x in items
        if x.last_worn and (now - x.last_worn).days >= 21 and x.status == "clean"
    ]
    laundry = [x for x in items if x.status in ("worn", "laundry")]

    if never:
        missions.append({
            "icon": "◈", "title": "Break the unworn streak",
            "text": f"Wear one of {len(never)} pieces you've never logged.",
            "action": "/wardrobe/", "action_text": "Find an unworn piece",
            "tone": "violet",
        })
    if idle:
        missions.append({
            "icon": "↻", "title": "Resurface a forgotten piece",
            "text": f"{len(idle)} clean pieces have been idle for 21+ days.",
            "action": "/outfits/", "action_text": "Build a fresh look",
            "tone": "amber",
        })
    if laundry:
        missions.append({
            "icon": "♧", "title": "Reset your rotation",
            "text": f"{len(laundry)} pieces are waiting in your care queue.",
            "action": "/laundry/", "action_text": "Open laundry",
            "tone": "blue",
        })
    if outfits:
        missions.append({
            "icon": "✦", "title": "Remix a saved favourite",
            "text": "Use a proven outfit as a starting point, then change one piece.",
            "action": "/outfits/", "action_text": "Open AI Stylist",
            "tone": "green",
        })
    return missions[:4]


def command_center(request):
    items_qs = scoped_items(request.user)
    outfits_qs = scoped_outfits(request.user)
    plans_qs = scoped_plans(request.user)

    items = list(items_qs)
    outfits = list(outfits_qs)
    now = timezone.now()

    total = len(items)
    worn = [x for x in items if x.wear_count > 0]
    clean = [x for x in items if x.status == "clean"]
    laundry = [x for x in items if x.status in ("worn", "laundry")]
    never = [x for x in items if x.wear_count == 0]
    idle = [
        x for x in items
        if x.last_worn and (now - x.last_worn).days >= 21 and x.status == "clean"
    ]

    utilization = (len(worn) / total * 100) if total else 0
    clean_rate = (len(clean) / total * 100) if total else 0

    categories = Counter(x.category for x in items)
    category_coverage = min(100, len(categories) * 12)
    families = Counter((x.color_family or "").lower() for x in items if x.color_family)
    color_diversity = min(100, len(families) * 18)

    wear_counts = [x.wear_count for x in worn]
    if wear_counts:
        avg_wear = sum(wear_counts) / len(wear_counts)
        rotation_balance = 100 if len(wear_counts) == 1 else max(
            0, 100 - ((max(wear_counts) - min(wear_counts)) / max(avg_wear, 1) * 12)
        )
    else:
        rotation_balance = 0

    feedback_total = sum(o.feedback_summary["total"] for o in outfits)
    feedback_score = min(100, feedback_total * 20)
    care_score = clean_rate

    pulse = _clamp(
        utilization * 0.28
        + rotation_balance * 0.22
        + category_coverage * 0.16
        + color_diversity * 0.14
        + care_score * 0.12
        + feedback_score * 0.08
    )

    if pulse >= 80:
        pulse_label = "In rhythm"
        pulse_text = "Your wardrobe is being used deliberately and has enough signal for strong recommendations."
    elif pulse >= 60:
        pulse_label = "Finding its rhythm"
        pulse_text = "A few small rotation and care changes can make the wardrobe more useful."
    elif pulse >= 40:
        pulse_label = "Needs a reset"
        pulse_text = "There is useful clothing data here, but several pieces are being left behind."
    else:
        pulse_label = "Just getting started"
        pulse_text = "Add a few pieces and log some wears to unlock better intelligence."

    wx = _weather()
    ootd = (recommend(items_qs, "casual", wx.get("temp", 25), wx.get("kind")) or [None])[0]

    upcoming = []
    for plan in plans_qs.filter(date__gte=timezone.localdate()).order_by("date")[:4]:
        upcoming.append({
            "date": plan.date,
            "occasion": plan.occasion,
            "location": plan.location,
        })

    capsule = _capsule(items, 10)
    capsule_families = Counter((x.color_family or "neutral").lower() for x in capsule)

    top_colors = Counter()
    for item in items:
        for entry in normalize_palette(item.palette)[:2]:
            top_colors[entry["name"]] += 1

    next_action = None
    if not items:
        next_action = {
            "title": "Build your first wardrobe signal",
            "text": "Add 5–8 everyday pieces. The engine can then start learning your palette, rotation and outfit compatibility.",
            "href": "/wardrobe/add/",
            "label": "Add your first piece",
        }
    elif never:
        next_action = {
            "title": "Give an ignored piece a chance",
            "text": f"You have {len(never)} clean pieces with zero logged wears. One real-world wear improves future rotation decisions.",
            "href": "/wardrobe/",
            "label": "Explore unworn pieces",
        }
    elif laundry:
        next_action = {
            "title": "Clear the care bottleneck",
            "text": f"{len(laundry)} pieces are outside the clean rotation. A quick laundry reset expands today's usable wardrobe.",
            "href": "/laundry/",
            "label": "Reset laundry",
        }
    elif idle:
        next_action = {
            "title": "Remix something you forgot",
            "text": f"{len(idle)} pieces have been quiet for at least three weeks. Let the stylist build around one.",
            "href": "/outfits/",
            "label": "Find a remix",
        }
    else:
        next_action = {
            "title": "Plan the next seven days",
            "text": "Your wardrobe is healthy enough to move from reactive outfit picking to intentional planning.",
            "href": "/planner/",
            "label": "Open weekly planner",
        }

    return render(request, "styleos/command_center.html", {
        "pulse": pulse,
        "pulse_label": pulse_label,
        "pulse_text": pulse_text,
        "pulse_metrics": [
            ("Utilization", round(utilization), "How much of your closet has been worn"),
            ("Rotation", round(rotation_balance), "How evenly wear is distributed"),
            ("Coverage", round(category_coverage), "Breadth across clothing categories"),
            ("Palette", round(color_diversity), "Variety in your detected color families"),
            ("Care", round(care_score), "Clean pieces ready to use"),
            ("Learning", round(feedback_score), "Signal from outfit feedback"),
        ],
        "items_count": total,
        "worn_count": len(worn),
        "never_count": len(never),
        "idle_count": len(idle),
        "laundry_count": len(laundry),
        "ootd": ootd,
        "weather": wx,
        "capsule": capsule,
        "capsule_families": capsule_families.items(),
        "missions": _missions(items, outfits),
        "next_action": next_action,
        "upcoming": upcoming,
        "top_colors": top_colors.most_common(6),
    })
