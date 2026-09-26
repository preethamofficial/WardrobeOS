from datetime import date,timedelta
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from config.scoping import scoped_plans

from .models import Plan


def weekly(request):
    start_date = date.today()
    days=[]
    for i in range(7):
        d=start_date+timedelta(days=i)
        days.append({"date":d,"plan":scoped_plans(request.user).filter(date=d).first()})
    return render(request,"planner/weekly.html",{"days":days})


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
    owner = request.user if request.user.is_authenticated else None
    if not occasion and not location:
        deleted, _ = scoped_plans(request.user).filter(date=plan_date).delete()
        messages.success(request, f"Plan for {plan_date.strftime('%b %d')} cleared."
                         if deleted else "No plan existed for that day.")
        return redirect("weekly")
    plan, created = Plan.objects.update_or_create(
        date=plan_date, owner=owner, defaults={"occasion": occasion, "location": location})
    messages.success(request, f"Plan for {plan_date.strftime('%b %d')} saved.")
    return redirect("weekly")
