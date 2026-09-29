"""Profile form - the city is geocoded so forecasts and packing stay accurate."""
from __future__ import annotations

from django import forms

from weather.service import geocode

from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "city", "country", "timezone", "currency", "temperature_unit", "theme"]
        widgets = {
            "city": forms.TextInput(attrs={"placeholder": "e.g. Bengaluru, Berlin, Austin, TX",
                                           "class": "input", "autocomplete": "address-level2"}),
            "temperature_unit": forms.Select(attrs={"class": "input"}),
        }
        labels = {"display_name": "Display name", "city": "Home city", "country": "Country", "timezone": "Time zone", "currency": "Currency", "temperature_unit": "Temperature unit", "theme": "Theme"}
        help_texts = {
            "city": "Used for live weather, outfit suggestions and trip packing lists.",
            "temperature_unit": "How temperatures are shown across the app.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["temperature_unit"].required = False
        self.fields["country"].required = False
        self.fields["display_name"].required = False
        self.fields["timezone"].required = False
        self.fields["currency"].required = False
        self._geo = None

    def clean_city(self):
        city = (self.cleaned_data.get("city") or "").strip()
        if not city:
            return ""
        geo = geocode(city)
        if not geo:
            raise forms.ValidationError(
                f"We could not find “{city}”. Try adding a state or country, "
                f"e.g. “Austin, TX” or “Pune, India”.")
        self._geo = geo
        return geo.get("name") or city

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self._geo:
            # Only overwrite coordinates when the city resolved successfully, so
            # an unchanged/blank field never wipes a good location.
            profile.latitude = self._geo["lat"]
            profile.longitude = self._geo["lon"]
            profile.country = self._geo.get("country", "") or profile.country
        if commit:
            profile.save()
        return profile


class DeleteAccountForm(forms.Form):
    """Typed confirmation + password, so deleting an account needs intent."""

    CONFIRM_PHRASE = "DELETE"

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}),
        label="Your password")
    confirm = forms.CharField(
        widget=forms.TextInput(attrs={"class": "input", "placeholder": CONFIRM_PHRASE,
                                      "autocomplete": "off"}),
        label=f'Type {CONFIRM_PHRASE} to confirm')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_confirm(self):
        value = (self.cleaned_data.get("confirm") or "").strip().upper()
        if value != self.CONFIRM_PHRASE:
            raise forms.ValidationError(f'Please type {self.CONFIRM_PHRASE} exactly.')
        return value

    def clean_password(self):
        password = self.cleaned_data.get("password") or ""
        if self.user is None or not self.user.check_password(password):
            raise forms.ValidationError("That password is not correct.")
        return password