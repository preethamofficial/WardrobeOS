"""Simple cache-based rate limiting for AI endpoints (no extra dependencies)."""
from __future__ import annotations

import os

from django.core.cache import cache
from django.http import JsonResponse


def _client_key(request) -> str:
    if request.session.session_key:
        return f"s:{request.session.session_key}"
    ident = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "anon"
    return f"ip:{ident}"


class RateLimitExceeded(Exception):
    pass


def check_rate_limit(request, bucket: str = "ai") -> None:
    """Raise RateLimitExceeded when the per-minute quota is exhausted."""
    limit = int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "12"))
    key = f"rl:{bucket}:{_client_key(request)}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, 60)
    if count > limit:
        raise RateLimitExceeded(
            f"Rate limit reached ({limit} requests/minute). Please wait a moment.")


def rate_limited_json_response(exc: RateLimitExceeded) -> JsonResponse:
    return JsonResponse({"ok": False, "error_code": "rate_limit",
                         "error": str(exc)}, status=429)
