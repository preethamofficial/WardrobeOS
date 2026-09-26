"""Wardrobe analytics: real value, utilisation and sustainability signals.

Cost-per-wear is the honest measure of a purchase decision, so it drives most of
this page: total wardrobe value, value tied up in never-worn pieces, the best and
worst cost-per-wear, category spend, and a three-part sustainability score
(utilisation, rotation balance, laundry health) with the components shown rather
than a single unexplained number. Wear history also surfaces "idle" pieces - worn
before, but not in a long time - which is where real value leaks out.
"""
import statistics
from datetime import timedelta

from django.shortcuts import render
from django.utils import timezone

from config.scoping import scoped_items

IDLE_DAYS = 90


def _value(item) -> float:
    try:
        return float(item.purchase_price or 0)
    except (TypeError, ValueError):
        return 0.0


def analytics(request):
    items = list(scoped_items(request.user))
    total = len(items)
    worn = [x for x in items if x.wear_count > 0]
    never = [x for x in items if not x.wear_count]
    clean = [x for x in items if x.status == "clean"]
    in_laundry = [x for x in items if x.status in ("worn", "laundry")]

    total_value = sum(_value(x) for x in items)
    total_wears = sum(x.wear_count for x in items)

    # --- cost per wear (only meaningful where a price was recorded) -------------
    priced = [x for x in items if _value(x) > 0]
    priced_value = sum(_value(x) for x in priced)
    cpw_rows = sorted(
        ({"name": x.name, "cpw": round(float(x.cost_per_wear), 2),
          "price": round(_value(x), 2), "wears": x.wear_count,
          "image": x.display_image} for x in priced),
        key=lambda d: d["cpw"])
    best_cpw = cpw_rows[:6]
    worst_cpw = sorted(cpw_rows, key=lambda d: d["cpw"], reverse=True)[:6]
    overall_cpw = round(priced_value / total_wears, 2) if priced_value and total_wears else None

    # --- category breakdown with spend ----------------------------------------
    categories: dict[str, dict] = {}
    for x in items:
        label = x.get_category_display()
        row = categories.setdefault(label, {"count": 0, "value": 0.0, "wears": 0})
        row["count"] += 1
        row["value"] += _value(x)
        row["wears"] += x.wear_count
    category_rows = [
        {"name": name, "count": row["count"], "value": round(row["value"], 2),
         "wears": row["wears"],
         "share": round(100 * row["count"] / total) if total else 0,
         "cpw": round(row["value"] / row["wears"], 2) if row["value"] and row["wears"] else None}
        for name, row in categories.items()]
    category_rows.sort(key=lambda d: d["value"], reverse=True)

    # --- what is being wasted ---------------------------------------------------
    idle_cutoff = timezone.now() - timedelta(days=IDLE_DAYS)
    idle = [x for x in items if x.last_worn and x.last_worn < idle_cutoff
            and x.status != "unavailable"]
    idle_value = sum(_value(x) for x in idle)
    never_value = sum(_value(x) for x in never)

    top = sorted(items, key=lambda x: x.wear_count, reverse=True)[:8]
    most_worn = top[0] if top else None

    # --- sustainability score, with the components visible ---------------------
    utilization = round(100 * len(worn) / total) if total else 0
    counts = [x.wear_count for x in worn]
    mean_w = statistics.mean(counts) if counts else 0
    spread = (statistics.pstdev(counts) / mean_w) if mean_w and len(counts) > 1 else 0
    balance = max(0, round(100 * (1 - spread))) if counts else 0
    laundry_health = round(100 * len(clean) / total) if total else 0
    sustainability = (round(0.5 * utilization + 0.3 * balance + 0.2 * laundry_health)
                      if total else 0)

    return render(request, "analytics/dashboard.html", {
        "total_items": total, "total_wears": total_wears, "used_items": len(worn),
        "never_items": never, "never_count": len(never), "never_value": round(never_value, 2),
        "top_items": top, "most_worn": most_worn,
        "categories": categories, "category_rows": category_rows,
        "cpw": cpw_rows[:6], "best_cpw": best_cpw, "worst_cpw": worst_cpw,
        "overall_cpw": overall_cpw, "priced_count": len(priced),
        "total_value": round(total_value, 2), "priced_value": round(priced_value, 2),
        "value_per_item": round(total_value / total, 2) if total else 0,
        "idle": idle[:10], "idle_count": len(idle), "idle_days": IDLE_DAYS,
        "idle_value": round(idle_value, 2),
        "in_laundry": len(in_laundry),
        "utilization": utilization, "balance": balance,
        "laundry_health": laundry_health, "sustainability": sustainability})

