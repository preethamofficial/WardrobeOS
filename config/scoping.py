"""Per-user data scoping helpers.

Local-first + multi-user: an anonymous visitor sees the shared "local"
wardrobe (records with owner = NULL), while a signed-in user sees ONLY their
own records. This keeps the app working as a single-user local tool and as a
hosted multi-user service without two code paths.
"""
from django.shortcuts import get_object_or_404

from laundry.models import WashLog  # noqa: F401  (isolated through Item.owner)
from outfits.models import Outfit
from planner.models import Plan
from trips.models import Trip
from wardrobe.models import Item


def scoped_items(user):
    if user.is_authenticated:
        return Item.objects.filter(owner=user)
    return Item.objects.filter(owner__isnull=True)


def scoped_outfits(user):
    if user.is_authenticated:
        return Outfit.objects.filter(owner=user)
    return Outfit.objects.filter(owner__isnull=True)


def scoped_plans(user):
    if user.is_authenticated:
        return Plan.objects.filter(owner=user)
    return Plan.objects.filter(owner__isnull=True)


def scoped_trips(user):
    if user.is_authenticated:
        return Trip.objects.filter(owner=user)
    return Trip.objects.filter(owner__isnull=True)


def get_scoped(qs, user, **filters):
    """get_object_or_404 that respects ownership (404 on foreign objects)."""
    if user.is_authenticated:
        filters["owner"] = user
    else:
        filters["owner__isnull"] = True
    return get_object_or_404(qs, **filters)