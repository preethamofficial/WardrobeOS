import random

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ai.matching import recommend
from config.scoping import scoped_items
from weather.service import get_weather, summarize

from .models import Outfit


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

@require_POST
def save_outfit(request):
    """Persist a recommended combo so it shows up in the wardrobe history."""
    occasion = request.POST.get("occasion", "casual")
    score = request.POST.get("score", "0")
    item_ids = [i for i in request.POST.get("items", "").split(",") if i.strip().isdigit()]
    items = list(scoped_items(request.user).filter(pk__in=item_ids))[:10]
    names = ", ".join(i.name for i in items) or "Outfit"
    outfit = Outfit.objects.create(name=f"{names}"[:120], occasion=occasion,
                                   score=float(score) if score.replace(".", "", 1).isdigit() else 0,
                                   owner=request.user if request.user.is_authenticated else None)
    outfit.items.set(items)
    messages.success(request, f"Saved \"{outfit.name}\" to your outfits.")
    return redirect("recommendations")
