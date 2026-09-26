import statistics

from django.shortcuts import render

from config.scoping import scoped_items


def analytics(request):
    items=list(scoped_items(request.user))
    worn=[x for x in items if x.wear_count>0]
    never=[x for x in items if not x.wear_count]
    clean=[x for x in items if x.status=="clean"]
    total_value=sum(float(x.purchase_price or 0) for x in items)
    cat_counts={}
    for x in items:
        cat_counts[x.get_category_display()]=cat_counts.get(x.get_category_display(),0)+1
    top=sorted(items,key=lambda x:x.wear_count,reverse=True)[:8]
    cpw=sorted([{"name":x.name,"cpw":round(float(x.cost_per_wear),2)} for x in worn if float(x.purchase_price)>0],key=lambda d:d["cpw"])[:6]
    utilization=round(100*len(worn)/len(items)) if items else 0
    counts=[x.wear_count for x in worn]
    mean_w=statistics.mean(counts) if counts else 0
    balance=round(100*(1-(statistics.pstdev(counts)/mean_w if mean_w and len(counts)>1 else 0)))
    laundry_health=round(100*len(clean)/len(items)) if items else 0
    sustainability=round(0.5*utilization+0.3*balance+0.2*laundry_health) if items else 0
    return render(request,"analytics/dashboard.html",{"total_items":len(items),"total_wears":sum(x.wear_count for x in items),
    "used_items":len(worn),"never_items":never,"top_items":top,"categories":cat_counts,"cpw":cpw,
    "total_value":total_value,"utilization":utilization,"balance":max(0,balance),
    "laundry_health":laundry_health,"sustainability":sustainability})
