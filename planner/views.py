from datetime import date,timedelta
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from config.scoping import scoped_plans

from .models import Plan


def weekly(request):
    raw_start = request.GET.get("week", "")
    try:
        start_date = date.fromisoformat(raw_start) if raw_start else date.today()
    except ValueError:
        start_date = date.today()
    days=[]
    for i in range(7):
        d=start_date+timedelta(days=i)
        days.append({"date":d,"plan":scoped_plans(request.user).filter(date=d).first()})
    return render(request,"planner/weekly.html",{"days":days, "start_date": start_date, "prev_start": start_date-timedelta(days=7), "next_start": start_date+timedelta(days=7)})


@require_POST
def add_plan(request):
    """Create/update the plan for one day; empty occasion+location clears it."""
    raw_date = request.POST.get("date", "")
    try:
        plan_date = date.fromisoformat(raw_date)
    except (TypeError, ValueError):
        messages.error(request, "Invalid date for the plan.")
        return redirect("weekly")
    occasion = (request.POST.get("occasion") or "").strip()[:80]
    location = (request.POST.get("location") or "").strip()[:120]
    notes = (request.POST.get("notes") or "").strip()[:1000]
    owner = request.user if request.user.is_authenticated else None
    if not occasion and not location:
        deleted, _ = scoped_plans(request.user).filter(date=plan_date).delete()
        messages.success(request, f"Plan for {plan_date.strftime('%b %d')} cleared."
                         if deleted else "No plan existed for that day.")
        return redirect("weekly")
    plan, created = Plan.objects.update_or_create(
        date=plan_date, owner=owner, defaults={"occasion": occasion, "location": location, "notes": notes})
    messages.success(request, f"Plan for {plan_date.strftime('%b %d')} saved.")
    return redirect("weekly")
\n\n@require_POST\ndef delete_plan(request, pk):\n    plan = scoped_plans(request.user).filter(pk=pk).first()\n    if plan:\n        plan.delete()\n        messages.success(request, "Planner entry deleted.")\n    return redirect("weekly")\n