"""Optional authentication wall.

Set LOGIN_REQUIRED=True in .env to require sign-in for every page except
the allow-list below. Default is off so the local-first experience is
unchanged; deployment configs can enable it with one variable.

Note: `/media/` is deliberately NOT allow-listed. Uploaded photos are served by
`wardrobe.media_views.serve_media`, which returns a file only to the account
that owns it, so a logged-out visitor (or a wrong account) gets a 404.
"""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect

ALLOWLIST_PREFIXES = ("/admin/login/", "/accounts/login/", "/accounts/signup/",
                      "/accounts/google/", "/accounts/3rdparty/",
                      "/static/", "/health/")


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "LOGIN_REQUIRED", False) and not request.user.is_authenticated:
            path = request.path
            if not any(path.startswith(p) for p in ALLOWLIST_PREFIXES):
                return redirect(f"/admin/login/?next={path}")
        return self.get_response(request)
