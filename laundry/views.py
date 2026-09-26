from django.contrib import messages
from django.shortcuts import redirect, render

from config.scoping import get_scoped, scoped_items

from wardrobe.models import Item

from .models import WashLog


def laundry_list(request):
    return render(request,"laundry/list.html",
                  {"items": scoped_items(request.user).filter(status__in=["worn","laundry"]).order_by("-wear_count")})

def mark_washed(request,pk):
    """Log a wash and put the item straight back into clean rotation."""
    item=get_scoped(Item.objects.all(),request.user,pk=pk)
    if request.method=="POST":
        WashLog.objects.create(item=item,notes="Washed from laundry center")
        item.status="clean"; item.save(update_fields=["status"])
        messages.success(request,f"{item.name} is fresh and back in rotation.")
    return redirect("laundry")
