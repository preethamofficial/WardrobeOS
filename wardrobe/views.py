from collections import Counter

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ai.colors import normalize_palette
from ai.matching import recommend
from config.scoping import get_scoped, scoped_items
from promptlab.services import lab_stats
from weather.service import get_weather, summarize

from .forms import ItemForm
from .models import Item
from .services import analyse_item


def _weather():
    try:
        return summarize(get_weather())
    except Exception:
        return None


def dashboard(request):
    items = scoped_items(request.user)
    wx = _weather()
    temp = (wx or {}).get("temp") or 25
    ootd = (recommend(items, "casual", temp, (wx or {}).get("kind")) or [None])[0]
    lab = lab_stats()
    # Wardrobe colour DNA: aggregate dominant named colours across palettes.
    dna = Counter()
    for pal in items.values_list("palette", flat=True):
        for i, entry in enumerate(normalize_palette(pal)[:2]):
            dna[(entry["hex"], entry["name"], entry["family"])] += (2 if i == 0 else 1)
    top_colors = [{"hex": k[0], "name": k[1], "family": k[2], "count": v}
                  for k, v in dna.most_common(8)]
    total = sum(c["count"] for c in top_colors) or 1
    for c in top_colors:
        c["pct"] = round(100 * c["count"] / total)
    return render(request, "dashboard.html", {
        "items_count": items.count(), "clean_count": items.filter(status="clean").count(),
        "laundry_count": items.filter(status="laundry").count(),
        "worn_count": items.filter(wear_count__gt=0).count(),
        "top_items": items.order_by("-wear_count")[:6], "ootd": ootd, "wx": wx,
        "lab": lab, "colour_dna": top_colors})


def wardrobe_list(request):
    q = (request.GET.get("q") or "").strip()
    cat = request.GET.get("category", "")
    status = request.GET.get("status", "")
    items = scoped_items(request.user).order_by("-created_at")
    if q:
        items = items.filter(name__icontains=q)
    if cat:
        items = items.filter(category=cat)
    if status:
        items = items.filter(status=status)
    page_obj = Paginator(items, 24).get_page(request.GET.get("page"))
    return render(request, "wardrobe/list.html", {
        "items": page_obj, "page_obj": page_obj, "categories": Item.CATEGORIES,
        "statuses": Item.STATUS, "q": q, "selected": cat, "selected_status": status})


def item_add(request):
    form = ItemForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if request.user.is_authenticated:
            item.owner = request.user
        item.save()
        if item.image:
            detection = analyse_item(item)
            palette = detection.get("palette") or []
            if palette:
                first = palette[0]
                messages.success(request, f"{item.name} added - detected {first['name']} ({first['family']}).")
            else:
                messages.success(request, f"{item.name} added (photo colours could not be read).")
        else:
            messages.success(request, f"{item.name} added. Add a photo to unlock auto colour detection.")
        return redirect("wardrobe_list")
    return render(request, "wardrobe/form.html", {"form": form, "title": "Add clothing"})
def _cleanup_replaced_files(item, previous_image):
    """Delete the orphaned image + thumbnail left by an upload replacement."""
    storage = item.image.storage
    try:
        if previous_image and previous_image != item.image.name and storage.exists(previous_image):
            storage.delete(previous_image)
        stem = previous_image.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
        old_thumb = f"wardrobe/thumbs/thumb_{stem}.jpg"
        current = item.thumbnail.name if item.thumbnail else ""
        if old_thumb != current and storage.exists(old_thumb):
            storage.delete(old_thumb)
    except Exception:
        pass


def item_edit(request, pk):
    item = get_scoped(Item.objects.all(), request.user, pk=pk)
    previous_image = item.image.name if item.image else ""
    form = ItemForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        if item.image and item.image.name != previous_image:
            # New photo: clean up the old files and re-run the full analysis.
            _cleanup_replaced_files(item, previous_image)
            detection = analyse_item(item)
            palette = detection.get("palette") or []
            if palette:
                first = palette[0]
                messages.success(request, f"Item updated - re-detected {first['name']} ({first['family']}).")
            else:
                messages.success(request, "Item updated.")
        else:
            messages.success(request, "Item updated.")
        return redirect("wardrobe_list")
    return render(request, "wardrobe/form.html", {"form": form, "title": "Edit clothing", "item": item})


@require_POST
def item_rescan(request, pk):
    """Re-run colour analysis on demand (button on the wardrobe grid)."""
    item = get_scoped(Item.objects.all(), request.user, pk=pk)
    if not item.image:
        messages.warning(request, "Add a photo first - colours are detected from images.")
        return redirect("wardrobe_list")
    result = analyse_item(item)
    palette = result.get("palette") or []
    if palette:
        first = palette[0]
        pct = round((result.get("confidence") or 0) * 100)
        messages.success(request, f"Re-scanned {item.name}: {first['name']} ({first['family']}), {pct}% confidence.")
    else:
        messages.error(request, f"Could not analyse the photo for {item.name}.")
    return redirect("wardrobe_list")


def item_delete(request, pk):
    item = get_scoped(Item.objects.all(), request.user, pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Item removed from your wardrobe.")
        return redirect("wardrobe_list")
    return render(request, "wardrobe/delete.html", {"item": item})


def item_wear(request, pk):
    item = get_scoped(Item.objects.all(), request.user, pk=pk)
    if request.method == "POST":
        item.wear()
        messages.success(request, f"Enjoy {item.name} - rotation updated.")
    return redirect("wardrobe_list")
