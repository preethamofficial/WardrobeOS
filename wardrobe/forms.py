from django import forms

from .models import Item
from .validators import ValidatedImageField, validate_image_upload


class ItemForm(forms.ModelForm):
    image = ValidatedImageField(
        validators=[validate_image_upload], required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
        help_text="JPEG, PNG or WebP. Colour, pattern and a preview are detected automatically.")

    category = forms.ChoiceField(choices=[("", "Select category")] + Item.CATEGORIES, required=True, widget=forms.Select(attrs={"class": "input"}))

    class Meta:
        model = Item
        fields = ["name", "image", "category", "brand", "size", "purchase_date", "care_instructions", "favorite", "tags", "color", "pattern", "material",
                  "formality", "season", "occasions", "status", "purchase_price", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Navy Oxford shirt", "class": "input"}),
            "color": forms.TextInput(attrs={"placeholder": "Leave blank to auto-detect from the photo", "class": "input"}),
            "pattern": forms.TextInput(attrs={"placeholder": "solid, stripes, checks... auto if blank", "class": "input"}),
            "material": forms.TextInput(attrs={"placeholder": "cotton, linen, denim...", "class": "input"}),
            "season": forms.TextInput(attrs={"placeholder": "all, summer, winter...", "class": "input"}),
            "occasions": forms.TextInput(attrs={"placeholder": "office, casual, party (comma separated)", "class": "input"}),
            "purchase_price": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "input"}),
            "purchase_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "care_instructions": forms.Textarea(attrs={"rows": 2, "class": "input"}),
            "brand": forms.TextInput(attrs={"class": "input", "placeholder": "Optional brand"}),
            "size": forms.TextInput(attrs={"class": "input", "placeholder": "Optional size"}),
            "tags": forms.TextInput(attrs={"class": "input", "placeholder": "work, favourite, travel"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "input"}),
        }
