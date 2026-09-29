"""Per-user preferences and the single source of truth for "where am I".

Everything weather-driven (dashboard pill, AI stylist, weekly planner, trip
packing lists, the JSON API) used to read DEFAULT_LATITUDE / DEFAULT_CITY from
the environment, which hard-coded one city for every visitor. Those values are
now only the *fallback*: a signed-in user's saved city wins.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.db import models

FALLBACK_LAT = 12.9716     # Bengaluru
FALLBACK_LON = 77.5946
FALLBACK_CITY = "Bengaluru"


class Profile(models.Model):
    """One row per user: home city + display preferences."""

    TEMP_UNITS = [("c", "Celsius (°C)"), ("f", "Fahrenheit (°F)")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="profile")
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    temperature_unit = models.CharField(max_length=1, choices=TEMP_UNITS, default="c")
    display_name = models.CharField(max_length=120, blank=True)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    currency = models.CharField(max_length=3, default="INR")
    theme = models.CharField(max_length=10, choices=[("light", "Light"), ("dark", "Dark"), ("system", "System")], default="system")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profile"
        verbose_name_plural = "profiles"

    def __str__(self):
        return f"{self.user.username} @ {self.city or 'unset'}"

    # -- construction ------------------------------------------------------------
    @classmethod
    def for_user(cls, user):
        """The user's profile, or None for anonymous visitors."""
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        profile, _ = cls.objects.get_or_create(user=user)
        return profile

    # -- derived values ----------------------------------------------------------
    @property
    def has_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def location_label(self) -> str:
        if self.city and self.country:
            return f"{self.city}, {self.country}"
        return self.city or self.country or FALLBACK_CITY

    def to_display(self, celsius):
        """Convert a Celsius reading to the unit this user prefers."""
        if celsius is None:
            return None
        if self.temperature_unit == "f":
            return round(celsius * 9 / 5 + 32)
        return round(celsius)


def resolve_location(user=None) -> dict:
    """Where to fetch weather for.

    Order: the signed-in user's saved city -> environment defaults -> Bengaluru.
    Returns {"lat", "lon", "city", "source"}.
    """
    profile = Profile.for_user(user)
    if profile and profile.has_location:
        return {"lat": profile.latitude, "lon": profile.longitude,
                "city": profile.location_label, "source": "profile"}
    try:
        lat = float(os.getenv("DEFAULT_LATITUDE", FALLBACK_LAT))
        lon = float(os.getenv("DEFAULT_LONGITUDE", FALLBACK_LON))
    except (TypeError, ValueError):
        lat, lon = FALLBACK_LAT, FALLBACK_LON
    return {"lat": lat, "lon": lon,
            "city": os.getenv("DEFAULT_CITY", FALLBACK_CITY).strip() or FALLBACK_CITY,
            "source": "default"}