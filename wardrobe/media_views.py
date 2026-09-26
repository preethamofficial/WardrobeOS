"""Authenticated media delivery.

Wardrobe photos are personal data: a public `/media/` prefix let anyone who
guessed (or was shown) a filename download somebody else's clothes, and under
`DEBUG=False` Django serves no media at all, so images 404'd in production.

Both problems are solved by one view: `/media/<path>` is now routed here in
every environment (development, Docker, Render, PythonAnywhere, ...) and the
file is only returned when the requester owns an item that references it.

Rules
-----
* Signed-in user  -> only files referenced by their own items.
* Anonymous       -> only files referenced by the shared local wardrobe
                     (owner = NULL), which keeps offline local-first use working.
* Staff/superuser -> any file (needed by the Django admin).
* Anything else   -> 404 (never 403, so filenames cannot be probed).
"""
from __future__ import annotations

import mimetypes
import posixpath

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET


def _clean_path(path: str) -> str:
    """Normalise a media-relative path and reject traversal attempts."""
    raw = str(path or "").replace("\\", "/").strip()
    normalised = posixpath.normpath(raw).lstrip("/")
    if not normalised or normalised.startswith("../") or "/../" in normalised \
            or normalised in (".", "..") or ":" in normalised:
        raise Http404("Not found.")
    return normalised


def _referenced_by(path: str, user) -> bool:
    """True when `path` belongs to an item this user is allowed to see."""
    from config.scoping import scoped_items

    if getattr(user, "is_staff", False):
        return True
    return scoped_items(user).filter(
        Q(image=path) | Q(thumbnail=path)).exists()


@require_GET
def serve_media(request, path):
    """Serve an uploaded file after an ownership check."""
    from django.core.files.storage import default_storage

    clean = _clean_path(path)
    if not _referenced_by(clean, request.user):
        raise Http404("Not found.")
    try:
        if not default_storage.exists(clean):
            raise Http404("Not found.")
        handle = default_storage.open(clean, "rb")
    except Http404:
        raise
    except Exception as exc:  # unreadable storage backend
        raise Http404("Not found.") from exc

    content_type, _ = mimetypes.guess_type(clean)
    response = FileResponse(handle, content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "private, max-age=86400"
    response["Content-Disposition"] = f'inline; filename="{posixpath.basename(clean)}"'
    response["X-Content-Type-Options"] = "nosniff"
    if settings.DEBUG:
        response["Content-Length"] = default_storage.size(clean)
    return response