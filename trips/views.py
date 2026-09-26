from datetime import date

from django.contrib import messages
from django.shortcuts import redirect,render

from config.scoping import get_scoped, scoped_items, scoped_trips
from weather.service import describe_code, geocode
from wardrobe.models import Item

from .models import Trip
from .packing import build, forecast_window


def _parse(value, fallback):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


def trip_list(request):
    return render(request,"trips/list.html",{"trips":scoped_trips(request.user).order_by("-start_date")})

def trip_create(request):
    today=date.today()
    if request.method=="POST":
        start=_parse(request.POST.get("start_date"),today)
        end=_parse(request.POST.get("end_date"),date.fromordinal(start.toordinal()+3))
        trip=Trip.objects.create(name=request.POST.get("name") or "My trip",
            destination=request.POST.get("destination") or "Somewhere nice",
            start_date=start,end_date=end,notes=request.POST.get("notes",""),
            owner=request.user if request.user.is_authenticated else None)
        geo=geocode(trip.destination)
        if geo:
            trip.lat,trip.lon=geo["lat"],geo["lon"]; trip.save(update_fields=["lat","lon"])
        trip.packing=build(trip,scoped_items(request.user)); trip.save(update_fields=["packing"])
        messages.success(request,f"Trip created - {len(trip.packing)} items on your packing list.")
        return redirect("trip_detail",pk=trip.pk)
    return render(request,"trips/form.html",{"title":"Plan a trip"})

def trip_detail(request,pk):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    days=forecast_window(trip.lat,trip.lon,trip.start_date.isoformat(),trip.end_date.isoformat()) \
        if (trip.lat is not None and trip.lon is not None) else []
    for d in days:
        label,emoji,_kind=describe_code(d["code"]); d["emoji"]=emoji; d["label"]=label
    grouped={}
    for entry in trip.packing:
        grouped.setdefault(entry.get("type","essential"),[]).append(entry)
    return render(request,"trips/detail.html",{"trip":trip,"days":days,"grouped":grouped})

def trip_toggle(request,pk,idx):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    if request.method=="POST":
        try:
            entry=trip.packing[int(idx)]; entry["packed"]=not entry.get("packed")
            trip.save(update_fields=["packing"])
        except (IndexError,TypeError,ValueError):
            pass
    return redirect("trip_detail",pk=trip.pk)

def trip_delete(request,pk):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    if request.method=="POST":
        trip.delete(); messages.success(request,"Trip removed.")
    return redirect("trips")
