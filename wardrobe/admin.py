from django.contrib import admin
from django.utils.html import format_html

from ai.colors import normalize_palette

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "color", "color_family", "formality",
                    "status", "wear_count", "ai_confidence", "color_swatch")
    list_filter = ("category", "formality", "status", "color_family")
    search_fields = ("name", "color", "pattern", "material")

    @admin.display(description="Detected colours")
    def color_swatch(self, obj):
        entries = normalize_palette(obj.palette)
        if not entries:
            return "-"
        chips = "".join(format_html(
            '<span title="{}" style="display:inline-block;width:16px;height:16px;'
            'border-radius:4px;margin-right:3px;background:{};border:1px solid #bbb"></span>',
            e["name"], e["hex"]) for e in entries[:4])
        return format_html('{} <small>{}</small>', chips, entries[0]["name"])
