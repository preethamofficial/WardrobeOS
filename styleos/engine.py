"""Deterministic style intelligence primitives.

All functions are pure/read-only over existing Item/Outfit/Plan objects.
They deliberately avoid network calls so the command center remains fast.
"""
from collections import Counter
from datetime import timedelta

from django.utils import timezone

from ai.matching import days_since


CATEGORY_GROUPS = {
    "tops": {"shirt", "tshirt"},
    "bottoms": {"pant", "jeans", "shorts", "skirt"},
    "layers": {"jacket", "hoodie", "sweater"},
    "one_piece": {"dress"},
    "shoes": {"shoes"},
}


def style_genome(items, outfits):
    items=list(items)
    outfits=list(outfits)
    total=len(items) or 1
    families=Counter((x.color_family or "unknown").lower() for x in items)
    formality=Counter(x.formality for x in items)
    patterns=Counter((x.pattern or "solid").lower() for x in items)
    materials=Counter((x.material or "unspecified").lower() for x in items)
    occasions=Counter()
    for x in items:
        occasions.update(v.strip().lower() for v in (x.occasions or "").split(",") if v.strip())

    preferred_formality=formality.most_common(1)[0][0] if formality else "casual"
    preferred_palette=families.most_common(4)
    preferred_pattern=patterns.most_common(1)[0][0] if patterns else "solid"
    dominant_occasion=occasions.most_common(1)[0][0] if occasions else "everyday"

    likes=dislikes=0
    for outfit in outfits:
        summary=outfit.feedback_summary
        likes += summary["likes"]
        dislikes += summary["dislikes"]

    return {
        "total": len(items),
        "palette": preferred_palette,
        "formality": preferred_formality,
        "pattern": preferred_pattern,
        "material": materials.most_common(3),
        "occasion": dominant_occasion,
        "feedback": {"likes": likes, "dislikes": dislikes, "total": likes+dislikes},
        "confidence": min(100, round((len(items)*5)+(likes+dislikes)*8)),
    }


def wardrobe_gaps(items):
    items=list(items)
    counts=Counter(x.category for x in items)
    clean=Counter(x.category for x in items if x.status=="clean")
    rules=[
        ("tshirt","T-shirts",3,"Everyday tops","High"),
        ("jeans","Jeans",2,"Reliable bottoms","Medium"),
        ("pant","Trousers / pants",2,"Bottom coverage","Medium"),
        ("shoes","Shoes",2,"Footwear variety","High"),
        ("jacket","Light layer",1,"Layering","Medium"),
        ("shirt","Shirts",2,"Smart-casual coverage","Medium"),
    ]
    gaps=[]
    for cat,label,target,reason,priority in rules:
        deficit=max(0,target-counts.get(cat,0))
        if deficit:
            gaps.append({"category":cat,"label":label,"missing":deficit,
                         "reason":reason,"priority":priority,
                         "clean":clean.get(cat,0)})
    return sorted(gaps,key=lambda x:(x["priority"]!="High",-x["missing"]))


def wardrobe_roi(items):
    items=list(items)
    total_spend=sum(float(x.purchase_price or 0) for x in items)
    total_wears=sum(x.wear_count for x in items)
    active=[x for x in items if x.wear_count]
    unused_value=sum(float(x.purchase_price or 0) for x in items if not x.wear_count)
    cpw=total_spend/total_wears if total_wears else total_spend
    best=sorted(active,key=lambda x:(x.wear_count, -(float(x.purchase_price or 0))),reverse=True)[:5]
    return {
        "spend":round(total_spend,2),"wears":total_wears,
        "cpw":round(cpw,2),"unused_value":round(unused_value,2),
        "active_pct":round(len(active)/(len(items) or 1)*100),
        "best":best,
    }


def remix_candidates(items, outfit, limit=6):
    """Find one-piece swaps that preserve the outfit's intent."""
    current=list(outfit.items.all()) if outfit is not None else []
    if not current:
        return []
    clean=list(items)
    current_ids={x.pk for x in current}
    out=[]
    for anchor in current:
        alternatives=[x for x in clean if x.pk not in current_ids and x.category==anchor.category and x.status=="clean"]
        alternatives.sort(key=lambda x:(days_since(x),x.wear_count),reverse=True)
        for alt in alternatives[:3]:
            out.append({"replace":anchor,"with":alt,
                        "reason":f"Swap {anchor.name} for {alt.name} to refresh the combination."})
    return out[:limit]


def capsule_for_trip(items, trip, max_pieces=12):
    """Compact travel capsule using the existing trip dates and wardrobe."""
    days=max(1,(trip.end_date-trip.start_date).days+1)
    clean=[x for x in items if x.status=="clean"]
    scored=[]
    for x in clean:
        score=0
        if x.category in {"tshirt","shirt","pant","jeans","shorts","dress","shoes"}: score+=10
        if x.formality=="casual": score+=3
        if x.wear_count==0: score+=4
        score += min(days_since(x),30)/30*4
        scored.append((score,x))
    scored.sort(key=lambda p:p[0],reverse=True)
    selected=[]
    categories=set()
    for _,x in scored:
        if len(selected)>=max_pieces: break
        if x.category not in categories or len(selected)<min(max_pieces,days+3):
            selected.append(x); categories.add(x.category)
    return selected


def seven_day_context(plans, daily_weather):
    by_date={p.date:p for p in plans}
    result=[]
    for day in daily_weather[:7]:
        result.append({
            "date":day.get("date"),
            "weather":day,
            "plan":by_date.get(day.get("date")),
        })
    return result
