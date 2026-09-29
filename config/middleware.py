"""Optional authentication wall.

Set LOGIN_REQUIRED=True in .env to require sign-in for every page except
the allow-list below. Default is off so the local-first experience is
unchanged; deployment configs can enable it with one variable.

Note: `/media/` is deliberately NOT allow-listed. Uploaded photos are served by
`wardrobe.media_views.serve_media`, which returns a file only to the account
that owns it, so a logged-out visitor (or a wrong account) gets a 404.
"""
from __future__ import annotations

from urllib.parse import quote

from django.conf import settings
from django.shortcuts import redirect

# The app's own allauth login/signup pages. `/admin/login/` is intentionally
# absent: the Django admin form is a staff tool, not the branded user login, and
# pointing ordinary visitors at it looks broken.
LOGIN_URL = "/accounts/login/"
SIGNUP_URL = "/accounts/signup/"

ALLOWLIST_PREFIXES = ("/admin/login/", LOGIN_URL, SIGNUP_URL,
                      "/accounts/google/", "/accounts/3rdparty/",
                      "/static/", "/health/", "/api/health/")


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "LOGIN_REQUIRED", False) and not request.user.is_authenticated:
            path = request.path
            if not any(path.startswith(p) for p in ALLOWLIST_PREFIXES):
                # `next` is URL-encoded so a crafted path cannot smuggle in a
                # scheme or host, and only same-site relative paths are returned.
                return redirect(f"{LOGIN_URL}?next={quote(path, safe='/')}")
        response = self.get_response(request)
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        response["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
