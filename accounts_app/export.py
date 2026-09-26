"""Personal data export (GDPR-style "download my data").

Builds one JSON document from every table that belongs to the signed-in user.
Images are not embedded (they can be large); their paths are listed instead, and
the user can download each photo from the wardrobe page because
`wardrobe.media_views` serves them to the owner only.
"""
from __future__ import annotations

from django.utils import timezone

from config.scoping import (scoped_ai_logs, scoped_analyses, scoped_items,
                            scoped_outfits, scoped_plans, scoped_prompts,
                            scoped_trips, scoped_workflow_runs)

SCHEMA_VERSION = 1


def _iso(value):
    return value.isoformat() if value else None


def _item_payload(item):
    price = float(item.purchase_price or 0)
    return {
        "id": item.pk, "name": item.name, "category": item.category,
        "color": item.color, "color_family": item.color_family,
        "pattern": item.pattern, "material": item.material,
        "formality": item.formality, "season": item.season,
        "occasions": item.occasions, "status": item.status,
        "wear_count": item.wear_count, "last_worn": _iso(item.last_worn),
        "purchase_price": str(item.purchase_price),
        "cost_per_wear": round(item.cost_per_wear, 2) if price else None,
        "palette": item.palette, "ai_confidence": item.ai_confidence,
        "ai_tagged": item.ai_tagged, "notes": item.notes,
        "image": item.image.name or None, "thumbnail": item.thumbnail.name or None,
        "created_at": _iso(item.created_at),
    }


def build_export(user) -> dict:
    """Everything we store about one user, as plain JSON-safe structures."""
    items = scoped_items(user)
    outfits = scoped_outfits(user)
    plans = scoped_plans(user)
    trips = scoped_trips(user)
    prompts = scoped_prompts(user)

    from laundry.models import WashLog

    wash_logs = WashLog.objects.filter(item__in=items).select_related("item")

    payload = {
        "export": {
            "app": "AI Smart Wardrobe OS",
            "schema_version": SCHEMA_VERSION,
            "generated_at": timezone.now().isoformat(),
            "note": "Photo files are listed by path but not embedded. "
                    "Download them from the wardrobe page while signed in.",
        },
        "account": {
            "username": user.username, "email": user.email,
            "first_name": user.first_name, "last_name": user.last_name,
            "is_staff": user.is_staff, "date_joined": _iso(user.date_joined),
            "last_login": _iso(user.last_login),
        },
        "profile": None,
        "wardrobe": {"count": items.count(), "items": [_item_payload(i) for i in items]},
        "outfits": [{
            "id": o.pk, "name": o.name, "occasion": o.occasion, "score": o.score,
            "favorite": o.favorite, "created_at": _iso(o.created_at),
            "items": [{"id": i.pk, "name": i.name, "category": i.category}
                      for i in o.items.all()],
            "feedback": [{"value": f.get_value_display(), "reason": f.reason,
                          "created_at": _iso(f.created_at)}
                         for f in o.feedback_set.all()],
        } for o in outfits],
        "planner": [{
            "id": p.pk, "date": _iso(p.date), "occasion": p.occasion,
            "location": p.location, "notes": p.notes,
        } for p in plans],
        "laundry": [{
            "item": w.item.name, "washed_at": _iso(w.washed_at), "notes": w.notes,
        } for w in wash_logs],
        "trips": [{
            "id": t.pk, "name": t.name, "destination": t.destination,
            "start_date": _iso(t.start_date), "end_date": _iso(t.end_date),
            "notes": t.notes, "packing": t.packing,
        } for t in trips],
        "prompt_lab": {
            "prompts": [{
                "id": p.pk, "title": p.title, "body": p.body, "goal": p.goal,
                "category": p.category, "tags": p.tags, "favorite": p.favorite,
                "use_count": p.use_count, "created_at": _iso(p.created_at),
                "versions": [{"version": v.version_number, "body": v.body,
                              "score": v.score, "change_note": v.change_note,
                              "created_at": _iso(v.created_at)}
                             for v in p.versions.all()],
            } for p in prompts],
            "analyses": [{"score": a.score, "created_at": _iso(a.created_at),
                          "report": a.report} for a in scoped_analyses(user)],
            "workflow_runs": [{"name": r.name, "preset": r.preset,
                               "final_score": r.final_score, "steps": r.steps,
                               "created_at": _iso(r.created_at)}
                              for r in scoped_workflow_runs(user)],
            "ai_request_log": [{"provider": l.provider, "model": l.model,
                                "status": l.status, "latency_ms": l.latency_ms,
                                "created_at": _iso(l.created_at)}
                               for l in scoped_ai_logs(user)],
        },
    }

    from .models import Profile

    profile = Profile.objects.filter(user=user).first()
    if profile:
        payload["profile"] = {
            "city": profile.city, "country": profile.country,
            "latitude": profile.latitude, "longitude": profile.longitude,
            "temperature_unit": profile.temperature_unit,
        }

    # Social identities (Google sign-in) - provider + which account, never tokens.
    try:
        from allauth.socialaccount.models import SocialAccount
        payload["connected_accounts"] = [{
            "provider": a.provider, "uid": a.uid,
            "last_login": _iso(a.last_login),
        } for a in SocialAccount.objects.filter(user=user)]
    except Exception:
        payload["connected_accounts"] = []
    return payload