from django.db import migrations, models


def forwards(apps, schema_editor):
    """Backfill legacy palettes: hex strings -> named entries + families."""
    Item = apps.get_model("wardrobe", "Item")
    from ai.colors import describe_color

    for item in Item.objects.exclude(image="").exclude(image=None).iterator():
        pal = item.palette
        changed = False
        if isinstance(pal, list) and pal and isinstance(pal[0], str):
            entries = []
            for hexv in pal[:5]:
                if not hexv:
                    continue
                d = describe_color(hexv)
                entries.append({"hex": d["hex"], "name": d["name"],
                                "family": d["family"], "share": 0.0})
            if entries:
                even = 1.0 / len(entries)
                for e in entries:
                    e["share"] = even
                item.palette = entries
                changed = True
        entries = item.palette if isinstance(item.palette, list) else []
        if entries and isinstance(entries[0], dict):
            if not (item.color_family or "").strip() and entries[0].get("family"):
                item.color_family = entries[0]["family"]
                changed = True
            if not (item.color or "").strip() and entries[0].get("name"):
                item.color = entries[0]["name"]
                changed = True
        if changed:
            item.save(update_fields=["palette", "color_family", "color"])


def backwards(apps, schema_editor):
    Item = apps.get_model("wardrobe", "Item")
    for item in Item.objects.iterator():
        pal = item.palette
        if isinstance(pal, list) and pal and isinstance(pal[0], dict):
            item.palette = [e.get("hex") for e in pal if isinstance(e, dict) and e.get("hex")]
            item.save(update_fields=["palette"])


class Migration(migrations.Migration):

    dependencies = [
        ("wardrobe", "0002_item_palette"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="color_family",
            field=models.CharField(blank=True, help_text="Colour family (blue, neutral, red...) derived from the photo - drives outfit rules", max_length=30),
        ),
        migrations.AddField(
            model_name="item",
            name="thumbnail",
            field=models.ImageField(blank=True, help_text="Small web preview generated on upload", null=True, upload_to="wardrobe/thumbs/"),
        ),
        migrations.RunPython(forwards, backwards),
    ]