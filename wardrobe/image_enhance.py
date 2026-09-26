"""Automatic image enhancement for uploaded wardrobe photos.

Runs on every upload before AI analysis: fixes EXIF orientation, flattens
transparency onto white, stretches contrast, adapts brightness to a target
exposure, boosts colour/sharpness and normalises size. Failures never block
an upload - the original file is kept untouched if enhancement errors out.
"""
from io import BytesIO

from django.core.files.base import ContentFile

from PIL import Image, ImageEnhance, ImageOps, ImageStat

MAX_DIMENSION = 1024
THUMB_DIMENSION = 480
TARGET_MEAN_LUMA = 124.0
CONTRAST_TRIGGER = 150.0  # only stretch photos flatter than this
ENHANCER_TAG = "WardrobeOS-Enhanced-v3"  # EXIF Software marker (idempotency)


def is_enhanced(path):
    """True when this file was already processed by this exact pipeline."""
    try:
        with Image.open(path) as im:
            return im.getexif().get(305) == ENHANCER_TAG
    except Exception:
        return False


def _contrast_spread(im):
    """Robust 1st-99th percentile luminance spread of the photo."""
    hist = im.convert("L").histogram()
    total = sum(hist) or 1

    def percentile(p):
        acc = 0
        target = total * p
        for i, count in enumerate(hist):
            acc += count
            if acc >= target:
                return i
        return 255

    return percentile(0.99) - percentile(0.01)


def _flatten_to_rgb(im):
    """Convert any mode to RGB, compositing transparency over white."""
    if im.mode == "RGB":
        return im
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return im.convert("RGB")


def _auto_exposure(im):
    """Correct only genuinely bad exposure - healthy colours stay untouched.

    Darkening bright photos shifts hue identity (navy drifts to black), so a
    dark photo is brightened, a blown-out photo is gently tamed, and anything
    with sane exposure is left alone.
    """
    mean = ImageStat.Stat(im.convert("L")).mean[0]
    if mean < 90:  # underexposed: brighten
        factor = max(1.0, min(1.45, TARGET_MEAN_LUMA / max(mean, 1)))
    elif mean > 170:  # blown out: gentle darken only
        factor = max(0.95, min(1.0, TARGET_MEAN_LUMA / mean))
    else:
        return im
    if abs(factor - 1) <= 0.02:
        return im
    return ImageEnhance.Brightness(im).enhance(factor)


def enhance_image(path):
    """Enhance a stored clothing photo in place. Returns True on success.

    Idempotent: a file tagged by a previous run is left untouched, so
    re-scans and re-uploads never double-process (which would shift colours,
    e.g. navy drifting toward black).
    """
    try:
        if is_enhanced(path):
            return True
        with Image.open(path) as im:
            im.load()
            fmt = (im.format or "JPEG").upper()
            im = ImageOps.exif_transpose(im)
            im = _flatten_to_rgb(im)
            # Autocontrast rescues washed-out photos, but on full-range photos
            # it crushes dark saturated garments (navy -> black). Apply it only
            # when the photo is genuinely flat.
            if _contrast_spread(im) < CONTRAST_TRIGGER:
                im = ImageOps.autocontrast(im, cutoff=1, preserve_tone=True)
            im = _auto_exposure(im)
            im = ImageEnhance.Color(im).enhance(1.12)
            if _contrast_spread(im) < CONTRAST_TRIGGER:
                im = ImageEnhance.Contrast(im).enhance(1.06)
            im = ImageEnhance.Sharpness(im).enhance(1.25)
            if max(im.size) > MAX_DIMENSION:
                im.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
            exif = im.getexif()
            exif[305] = ENHANCER_TAG
            try:
                im.save(path, format=fmt, quality=90, exif=exif.tobytes(),
                        optimize=fmt in ("JPEG", "PNG", "WEBP"))
            except (OSError, ValueError):
                im.save(path, format="JPEG", quality=90, exif=exif.tobytes())
        return True
    except Exception:
        return False


def build_thumbnail(src_path):
    """Create a small web preview.

    Returns (filename, ContentFile) ready for an ImageField.save(), or None
    when the source cannot be read. Thumbnails keep the aspect ratio and are
    always JPEG so lists and grids stay fast on real-world photo sizes.
    """
    try:
        with Image.open(src_path) as im:
            im.load()
            im = ImageOps.exif_transpose(im)
            im = _flatten_to_rgb(im)
            if max(im.size) > THUMB_DIMENSION:
                im.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION), Image.Resampling.LANCZOS)
            im = ImageEnhance.Sharpness(im).enhance(1.1)
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=85, optimize=True)
        name = "thumb_" + str(src_path).replace("\\", "/").rsplit("/", 1)[-1]
        name = name.rsplit(".", 1)[0] + ".jpg"
        return name, ContentFile(buf.getvalue())
    except Exception:
        return None