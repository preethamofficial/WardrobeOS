"""Re-run colour analysis across the wardrobe (backfill tool).

Usage:
    python manage.py reanalyze_wardrobe
    python manage.py reanalyze_wardrobe --missing-only
    python manage.py reanalyze_wardrobe --limit 5
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from wardrobe.models import Item
from wardrobe.services import analyse_item


class Command(BaseCommand):
    help = ("Re-extract palettes, colour names, colour families, patterns and "
            "thumbnails for every stored wardrobe photo.")

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0,
                            help="Only process the first N items (0 = all).")
        parser.add_argument("--missing-only", action="store_true",
                            help="Only items with no palette or no colour family yet.")

    def handle(self, *args, **options):
        qs = Item.objects.exclude(image="").exclude(image=None).order_by("id")
        if options["missing_only"]:
            qs = qs.filter(Q(palette=[]) | Q(palette=None) | Q(color_family=""))
        if options["limit"]:
            qs = qs[: options["limit"]]
        total = qs.count()
        if not total:
            self.stdout.write(self.style.WARNING("Nothing to analyse."))
            return
        done = 0
        for item in qs:
            result = analyse_item(item)
            done += 1
            palette = result.get("palette") or []
            if palette:
                first = palette[0]
                detail = f"{first['name']} ({first['family']}) - {round(first['share'] * 100)}%"
            else:
                detail = "no colours found"
            self.stdout.write(f"[{done}/{total}] {item.name}: {detail}")
        self.stdout.write(self.style.SUCCESS(f"Re-analysed {done}/{total} items."))