from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from config.scoping import get_scoped, scoped_items

from wardrobe.models import Item

from .models import WashLog


def _queue(user):
    return scoped_items(user).filter(status__in=["worn", "laundry"]).order_by("-wear_count")


def laundry_list(request):
    return render(request, "laundry/list.html", {"items": _queue(request.user)})


@require_POST
def mark_washed(request,pk):
    """Log a wash and put the item straight back into clean rotation."""
    item=get_scoped(Item.objects.all(),request.user,pk=pk)
    WashLog.objects.create(item=item,notes="Washed from laundry center")
    item.status="clean"; item.save(update_fields=["status"])
    messages.success(request,f"{item.name} is fresh and back in rotation.")
    return redirect("laundry")


@require_POST
def mark_all_washed(request):
    """Empty the whole queue in one action (weekly laundry day)."""
    items = list(_queue(request.user))
    if not items:
        messages.info(request, "Your laundry queue is already clear.")
        return redirect("laundry")
    for item in items:
        WashLog.objects.create(item=item, notes="Bulk wash from laundry center")
    Item.objects.filter(pk__in=[i.pk for i in items]).update(status="clean")
    messages.success(request,
                     f"Marked {len(items)} item{'' if len(items) == 1 else 's'} washed - "
                     f"everything is back in rotation.")
    return redirect("laundry")
