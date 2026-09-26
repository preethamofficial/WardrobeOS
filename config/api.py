"""Read-only JSON API - same engine as the UI, ready for mobile clients.

`/api/items/` is paginated so a large wardrobe never ships one enormous
response: pass `?page=2&page_size=50`. Envelope keys (`count`, `page`,
`pages`, `page_size`, `has_next`) stay stable for clients.
"""
from django.core.paginator import EmptyPage, Paginator
from django.db import connection
from django.http import JsonResponse

from ai.matching import recommend
from config.scoping import scoped_items
from weather.service import get_weather, summarize

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _page_size(request) -> int:
    try:
        requested = int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return max(1, min(MAX_PAGE_SIZE, requested))


def items(request):
    queryset = scoped_items(request.user).order_by("-created_at", "-pk")
    size = _page_size(request)
    paginator = Paginator(queryset, size)
    try:
        page_number = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page_number = 1
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages) if paginator.num_pages else None

    rows = page.object_list if page is not None else []
    data = [{"id": x.id, "name": x.name, "category": x.category, "color": x.color,
             "color_family": x.color_family, "pattern": x.pattern,
             "formality": x.formality, "status": x.status, "wear_count": x.wear_count,
             "palette": x.palette, "cost_per_wear": x.cost_per_wear,
             "image": request.build_absolute_uri(x.image.url) if x.image else None,
             "thumbnail": request.build_absolute_uri(x.thumbnail.url) if x.thumbnail else None}
            for x in rows]
    return JsonResponse({
        "count": paginator.count,
        "page": page.number if page is not None else 1,
        "pages": paginator.num_pages,
        "page_size": size,
        "has_next": bool(page.has_next()) if page is not None else False,
        "has_previous": bool(page.has_previous()) if page is not None else False,
        "items": data,
    })


def weather_now(request):
    try:
        return JsonResponse(summarize(get_weather()))
    except Exception:
        return JsonResponse({"error": "weather unavailable"}, status=503)


def outfit_today(request):
    try:
        wx = summarize(get_weather())
    except Exception:
        wx = {}
    temp = wx.get("temp") if wx.get("temp") is not None else 25
    outfits = recommend(scoped_items(request.user), request.GET.get("occasion", "casual"), temp, wx.get("kind"))
    return JsonResponse({
        "weather": {"temp": temp, "label": wx.get("label"), "kind": wx.get("kind")},
        "outfits": [{"score": o["score"], "why": o["why"], "palette": o["palette"],
                     "items": [{"id": i.id, "name": i.name, "category": i.category,
                                "color": i.color, "color_family": i.color_family}
                               for i in o["items"]]}
                    for o in outfits]})


def health(request):
    """Ops endpoint for uptime checks / load balancers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception as exc:
        db = f"error: {exc}"
    return JsonResponse({"status": "ok" if db == "ok" else "degraded",
                         "database": db, "app": "ai-smart-wardrobe-os"})