"""Upload validation for wardrobe photos.

An unvalidated image upload is three risks at once: disk/bandwidth abuse (a
40 MB "photo"), decompression bombs (a 100k x 100k PNG that explodes in RAM the
moment Pillow touches it) and stored corruption (a truncated JPEG that breaks
every later enhancement pass).

`validate_image_upload` is attached to `ItemForm.image`, so the checks run
before anything is written to storage. Limits are configurable through the
environment (see .env.example).
"""
from __future__ import annotations

import os

from django import forms
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

# Formats a browser can display directly and Pillow can decode without plugins.
ALLOWED_FORMATS = {"JPEG", "JPG", "MPO", "PNG", "WEBP", "BMP", "TIFF", "GIF"}
HEIF_HINT = ("iPhone HEIC/HEIF photos are not decodable by the default Pillow "
             "build. Set the camera/phone option to 'Most Compatible' or export "
             "the photo as JPEG, then upload again.")

MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_IMAGE_MB", "8")) * 1024 * 1024)
MAX_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))     # 40 MP ceiling
MAX_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "8000"))             # px per side
MIN_SIDE = int(os.getenv("MIN_IMAGE_SIDE", "64"))               # reject icons


def _human_mb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def validate_image_upload(uploaded):
    """Reject oversized, corrupt, exotic or absurdly large images."""
    if uploaded is None:
        return uploaded
    size = getattr(uploaded, "size", 0) or 0
    if size == 0:
        raise ValidationError("That file is empty. Please choose a photo again.")
    if size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"That photo is {_human_mb(size)}; the limit is "
            f"{_human_mb(MAX_UPLOAD_BYTES)}. Resize it and try again.")

    filename = (getattr(uploaded, "name", "") or "").lower()
    if filename.endswith((".heic", ".heif")):
        raise ValidationError(HEIF_HINT)

    # Decode the whole stream: `verify()` is what catches truncation, and it must
    # run before the file is read for anything else.
    try:
        uploaded.seek(0)
        with Image.open(uploaded) as probe:
            image_format = (probe.format or "").upper()
            width, height = probe.size
            probe.verify()
    except UnidentifiedImageError as exc:
        raise ValidationError(
            "That file is not a readable image. JPEG, PNG or WebP please."
        ) from exc
    except Exception as exc:
        raise ValidationError(
            "That image appears corrupt or half-uploaded - please try again."
        ) from exc
    finally:
        try:
            uploaded.seek(0)
        except Exception:
            pass

    if image_format and image_format not in ALLOWED_FORMATS:
        raise ValidationError(
            f"{image_format} images are not supported. Use JPEG, PNG or WebP.")

    pixels = width * height
    if pixels > MAX_PIXELS:
        raise ValidationError(
            f"That image is {width}x{height} ({pixels / 1_000_000:.0f} MP); the "
            f"limit is {MAX_PIXELS / 1_000_000:.0f} MP.")
    if max(width, height) > MAX_SIDE:
        raise ValidationError(
            f"That image is {width}x{height}px; each side must be {MAX_SIDE}px or less.")
    if min(width, height) < MIN_SIDE:
        raise ValidationError(
            f"That image is only {width}x{height}px - too small to identify. "
            f"Each side must be at least {MIN_SIDE}px.")
    return uploaded


class ValidatedImageField(forms.ImageField):
    """ImageField that enforces cheap checks BEFORE Pillow tries to decode.

    Django's `ImageField.to_python()` opens the stream immediately and raises a
    generic "Upload a valid image." for anything it cannot decode - which would
    hide our friendlier size and HEIC messages (a 9 MB blob or a `.heic` file
    fails decoding first). Checking the filename and byte size up front keeps
    the specific errors visible; dimension/corruption checks still run later as
    regular validators.
    """

    def to_python(self, data):
        if data in self.empty_values:
            return None
        filename = (getattr(data, "name", "") or "").lower()
        if filename.endswith((".heic", ".heif")):
            raise ValidationError(HEIF_HINT)
        size = getattr(data, "size", 0) or 0
        if size == 0:
            raise ValidationError("That file is empty. Please choose a photo again.")
        if size > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"That photo is {_human_mb(size)}; the limit is "
                f"{_human_mb(MAX_UPLOAD_BYTES)}. Resize it and try again.")
        return super().to_python(data)