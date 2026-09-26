from datetime import date

from django.contrib import messages
from django.shortcuts import redirect,render
from django.views.decorators.http import require_POST

from config.scoping import get_scoped, owner_of, scoped_items, scoped_trips
from weather.service import describe_code, geocode

from .forms import TripForm, default_dates
from .models import Trip
from .packing import build, forecast_window


def trip_list(request):
    return render(request,"trips/list.html",{"trips":scoped_trips(request.user).order_by("-start_date")})


def _refresh_packing(request, trip):
    """Recompute the packing list from the current wardrobe + forecast."""
    trip.packing = build(trip, scoped_items(request.user))
    trip.save(update_fields=["packing"])
    return trip


def _locate(trip):
    """Resolve the destination to coordinates so forecasts work."""
    geo = geocode(trip.destination)
    if geo:
        trip.lat, trip.lon = geo["lat"], geo["lon"]
    else:
        trip.lat, trip.lon = None, None
    return trip


def trip_create(request):
    if request.method == "POST":
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save(commit=False)
            trip.owner = owner_of(request.user)
            _locate(trip)
            trip.save()
            _refresh_packing(request, trip)
            messages.success(request, f"Trip created - {len(trip.packing)} items on your packing list.")
            return redirect("trip_detail", pk=trip.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = TripForm(initial=default_dates())
    return render(request, "trips/form.html", {"form": form, "title": "Plan a trip",
                                               "mode": "create"})


def trip_edit(request, pk):
    trip = get_scoped(Trip.objects.all(), request.user, pk=pk)
    if request.method == "POST":
        form = TripForm(request.POST, instance=trip)
        if form.is_valid():
            trip = form.save()
            _locate(trip)
            trip.save(update_fields=["lat", "lon"])
            _refresh_packing(request, trip)
            messages.success(request, "Trip updated and packing list rebuilt.")
            return redirect("trip_detail", pk=trip.pk)
        messages.error(request, "Please fix the errors below.")
    else:
        form = TripForm(instance=trip)
    return render(request, "trips/form.html", {"form": form, "title": f"Edit {trip.name}",
                                               "mode": "edit", "trip": trip})


def trip_detail(request,pk):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    days=forecast_window(trip.lat,trip.lon,trip.start_date.isoformat(),trip.end_date.isoformat()) \
        if (trip.lat is not None and trip.lon is not None) else []
    for d in days:
        label,emoji,_kind=describe_code(d["code"]); d["emoji"]=emoji; d["label"]=label
    grouped={}
    for idx, entry in enumerate(trip.packing):
        entry = dict(entry)
        entry["index"] = idx
        grouped.setdefault(entry.get("type","essential"),[]).append(entry)
    return render(request,"trips/detail.html",{"trip":trip,"days":days,"grouped":grouped})


@require_POST
def trip_toggle(request,pk,idx):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    try:
        entry=trip.packing[int(idx)]; entry["packed"]=not entry.get("packed")
        trip.save(update_fields=["packing"])
    except (IndexError,TypeError,ValueError):
        pass
    return redirect("trip_detail",pk=trip.pk)


@require_POST
def trip_refresh(request, pk):
    """Rebuild the packing list (new wardrobe items, updated forecast)."""
    trip = get_scoped(Trip.objects.all(), request.user, pk=pk)
    _locate(trip)
    trip.save(update_fields=["lat", "lon"])
    _refresh_packing(request, trip)
    messages.success(request, "Packing list rebuilt from your wardrobe and forecast.")
    return redirect("trip_detail", pk=trip.pk)


@require_POST
def trip_delete(request,pk):
    trip=get_scoped(Trip.objects.all(),request.user,pk=pk)
    trip.delete(); messages.success(request,"Trip removed.")
    return redirect("trips")
