import random

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai.matching import recommend
from config.scoping import get_scoped, owner_of, scoped_items, scoped_outfits
from weather.service import get_weather, summarize

from .models import Feedback, Outfit

MAX_SAVED_ITEMS = 10
FEEDBACK_REASONS = dict(Feedback.REASONS)


def _wx():
    try:
        return summarize(get_weather())
    except Exception:
        return {"temp": 25, "kind": None, "label": "unavailable", "emoji": "🌡️",
                "rainy": False, "hot": False, "cold": False, "precip_prob": None}


def recommendations(request):
    occasion=request.GET.get("occasion","office")
    wx=_wx()
    results=recommend(scoped_items(request.user),occasion,wx.get("temp",25),wx.get("kind"))
    return render(request,"outfits/recommendations.html",{"outfits":results,"occasion":occasion,"weather":wx})

def shuffle(request):
    """Random good combo for the chosen occasion - the 'dress me' button."""
    occasion=request.GET.get("occasion","casual")
    wx=_wx()
    results=recommend(scoped_items(request.user),occasion,wx.get("temp",25),wx.get("kind"))
    pick=random.choice(results) if results else None
    return render(request,"outfits/recommendations.html",
        {"outfits":[pick] if pick else [],"occasion":occasion,"weather":wx,"shuffled":True})

def _score_value(raw) -> float:
    """Clamp a posted score to 0-100; junk input becomes 0 instead of crashing."""
    try:
        return max(0.0, min(100.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


@require_POST
def save_outfit(request):
    """Persist a recommended combo so it shows up in the outfit history."""
    occasion = request.POST.get("occasion", "casual")
    score = request.POST.get("score", "0")
    item_ids = [i for i in request.POST.get("items", "").split(",") if i.strip().isdigit()]
    items = list(scoped_items(request.user).filter(pk__in=item_ids))[:MAX_SAVED_ITEMS]
    names = ", ".join(i.name for i in items) or "Outfit"
    outfit = Outfit.objects.create(name=f"{names}"[:120], occasion=occasion,
                                   score=_score_value(score),
                                   owner=owner_of(request.user))
    outfit.items.set(items)
    messages.success(request, f"Saved {outfit.name!r} to your outfits.")
    return redirect("outfit_history")


def outfit_history(request):
    """Every saved outfit, filterable, with its wear + feedback stats."""
    base = scoped_outfits(request.user)
    outfits = base.prefetch_related("items")
    occasion = (request.GET.get("occasion") or "").strip()
    if occasion:
        outfits = outfits.filter(occasion=occasion)
    favorites_only = request.GET.get("favorites") == "1"
    if favorites_only:
        outfits = outfits.filter(favorite=True)
    occasions = sorted({o for o in base.values_list("occasion", flat=True) if o})
    total = base.count()
    stats = {
        "total": total,
        "favorites": base.filter(favorite=True).count(),
        "wears": sum(base.values_list("wear_count", flat=True)),
        "avg_score": round(sum(base.values_list("score", flat=True)) / total) if total else 0,
    }
    return render(request, "outfits/history.html",
                  {"outfits": outfits, "occasion": occasion, "occasions": occasions,
                   "favorites_only": favorites_only, "stats": stats})


def _outfit_for(request, pk):
    return get_scoped(Outfit.objects.all(), request.user, pk=pk)


@require_POST
def favorite_outfit(request, pk):
    outfit = _outfit_for(request, pk)
    outfit.favorite = not outfit.favorite
    outfit.save(update_fields=["favorite"])
    messages.success(request, f"{outfit.name!r} is "
                              f"{'now a favourite' if outfit.favorite else 'no longer a favourite'}.")
    return redirect(request.POST.get("next") or "outfit_history")


@require_POST
def mark_outfit_worn(request, pk):
    """Wear the whole combination: bumps the outfit *and* every item in it."""
    outfit = _outfit_for(request, pk)
    outfit.mark_worn(timezone.now())
    messages.success(request, f"Logged a wear of {outfit.name!r} - "
                              f"{outfit.item_count} item(s) moved to the laundry queue.")
    return redirect(request.POST.get("next") or "outfit_history")


@require_POST
def delete_outfit(request, pk):
    outfit = _outfit_for(request, pk)
    name = outfit.name
    outfit.delete()
    messages.success(request, f"Removed {name!r} from your outfits.")
    return redirect("outfit_history")


def outfit_feedback(request, pk):
    """Like/dislike a saved outfit with an optional reason and note."""
    outfit = _outfit_for(request, pk)
    if request.method == "POST":
        raw = request.POST.get("value", "")
        if raw not in ("1", "-1"):
            messages.error(request, "Choose either a like or a dislike.")
            return redirect("outfit_feedback", pk=outfit.pk)
        reason = (request.POST.get("reason") or "").strip()
        Feedback.objects.create(
            outfit=outfit, value=int(raw),
            reason=reason if reason in FEEDBACK_REASONS else "",
            note=(request.POST.get("note") or "").strip()[:240])
        messages.success(request, "Thanks - the stylist will use that next time.")
        return redirect("outfit_history")
    return render(request, "outfits/feedback.html",
                  {"outfit": outfit, "reasons": Feedback.REASONS,
                   "summary": outfit.feedback_summary})
