"""Trip form with real validation (dates, length, sane field bounds)."""
from __future__ import annotations

from datetime import date, timedelta

from django import forms

from .models import Trip

MAX_TRIP_DAYS = 120
_DATE_WIDGET = forms.DateInput(attrs={"type": "date", "class": "input"})


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ["name", "destination", "start_date", "end_date", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Diwali in Goa", "class": "input"}),
            "destination": forms.TextInput(attrs={"placeholder": "City or town, e.g. Panaji, Goa",
                                                  "class": "input"}),
            "start_date": _DATE_WIDGET,
            "end_date": _DATE_WIDGET,
            "notes": forms.Textarea(attrs={"rows": 3, "class": "input",
                                           "placeholder": "Anything the packing list should know"}),
        }
        labels = {"name": "Trip name", "destination": "Destination",
                  "start_date": "Start date", "end_date": "End date", "notes": "Notes"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["start_date"].widget.attrs.setdefault("min", date.today().isoformat())
        # The model field is required, so a blank destination would raise Django's
        # generic "This field is required." before clean_destination could run.
        # Lift the field-level requirement and enforce our friendlier message there.
        self.fields["destination"].required = False

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        return name or "My trip"

    def clean_destination(self):
        destination = (self.cleaned_data.get("destination") or "").strip()
        if not destination:
            raise forms.ValidationError("Where are you going? A city name lets us "
                                        "fetch the forecast and pack for the weather.")
        return destination

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end:
            if end < start:
                self.add_error("end_date",
                               "The end date cannot be before the start date.")
            elif (end - start).days > MAX_TRIP_DAYS:
                self.add_error("end_date",
                               f"That is longer than {MAX_TRIP_DAYS} days - please split it "
                               f"into shorter trips so the packing list stays useful.")
        return cleaned

    def packing_window(self) -> tuple[date, date] | None:
        if self.is_valid():
            return self.cleaned_data["start_date"], self.cleaned_data["end_date"]
        return None


def default_dates() -> dict:
    today = date.today()
    return {"start_date": today, "end_date": today + timedelta(days=3)}