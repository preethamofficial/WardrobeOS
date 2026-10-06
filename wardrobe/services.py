"""Shared image-processing pipeline for wardrobe items.

Used by the upload views, the per-item re-scan action and the
`reanalyze_wardrobe` management command so every path applies exactly the
same enhancement + colour analysis steps.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from django.core.files import File
from django.core.files.storage import default_storage

from ai.colors import extract_palette
from ai.orchestrator import analyze_clothing

from .image_enhance import build_thumbnail, enhance_image

log = logging.getLogger("wardrobe")


def _materialize_image(item):
    """Copy a stored image to a local temp file for PIL/AI processing."""
    suffix = Path(item.image.name or "").suffix.lower() or ".jpg"
    handle = default_storage.open(item.image.name, "rb")
    temp = tempfile.NamedTemporaryFile(prefix="wardrobe-", suffix=suffix, delete=False)
    try:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            temp.write(chunk)
        temp.flush()
        return temp.name
    finally:
        temp.close()
        try:
            handle.close()
        except Exception:
            pass


def _refresh_thumbnail(item, local_path):
    """Regenerate item.thumbnail from a local processing copy."""
    if item.thumbnail:
        try:
            item.thumbnail.delete(save=False)
        except Exception:
            pass
    item.thumbnail = None
    built = build_thumbnail(local_path)
    if built:
        name, content = built
        item.thumbnail.save(name, content, save=False)


def _save_processed_image(item, local_path):
    """Upload the enhanced local copy through Django storage."""
    stored_name = item.image.name
    with open(local_path, "rb") as source:
        item.image.save(stored_name, File(source), save=False)


def analyse_item(item, *, auto_color=True):
    """Enhance + thumbnail + colour analysis for one item, then persist.

    Returns a dict: {"ok", "palette", "provider", "pattern", "confidence"}.
    Never raises - uploads must not break because analysis did.
    """
    result = {"ok": False, "palette": [], "provider": "local",
              "pattern": "", "confidence": 0.0}
    if not item.image:
        return result
    local_path = None
    try:
        local_path = _materialize_image(item)
        enhance_image(local_path)
        _save_processed_image(item, local_path)
        _refresh_thumbnail(item, local_path)
        analysis = analyze_clothing(local_path)
        palette = analysis.get("palette") or extract_palette(item.image.path)
        item.palette = palette
        if palette:
            item.color_family = (palette[0].get("family") or "").strip() or item.color_family
            if auto_color and not (item.color or "").strip():
                item.color = (palette[0].get("name") or "").strip() or item.color
        if auto_color and not (item.pattern or "").strip() and analysis.get("pattern"):
            item.pattern = analysis["pattern"]
        for field in ("category", "material", "formality"):
            value = analysis.get(field)
            if value and not (getattr(item, field) or "").strip():
                setattr(item, field, value)
        item.ai_confidence = analysis.get("confidence", 0)
        item.ai_tagged = analysis.get("provider", "local") not in ("", "local")
        item.save(update_fields=[
            "palette", "color_family", "color", "pattern", "category",
            "material", "formality", "ai_confidence", "ai_tagged", "thumbnail"])
        result.update(ok=True, palette=palette,
                      provider=analysis.get("provider", "local"),
                      pattern=analysis.get("pattern", ""),
                      confidence=analysis.get("confidence", 0))
    except Exception:
        log.exception("Colour analysis failed for item %s", item.pk)
    finally:
        if local_path:
            try:
                os.unlink(local_path)
            except OSError:
                pass
    return result