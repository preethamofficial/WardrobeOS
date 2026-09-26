"""Database-backed rate limiting for AI endpoints (no extra dependencies).

Why the database: the previous implementation used Django's *default* cache,
which is process-local memory. Behind gunicorn/uvicorn every worker had its own
counter (quota x workers) and a restart wiped the counters. The counter lives in
one shared row per (key, window) in `promptlab.RateBucket`, which is atomic
across workers and survives restarts - no Redis needed for a small deployment.
Setting `REDIS_URL` enables a Redis cache for other caching, but the counters
still come from these rows so the quota stays correct.

Keying order: authenticated user > session > remote address. `X-Forwarded-For`
is only consulted when TRUST_PROXY_HEADERS is explicitly enabled, because that
header is client-controlled and trivially spoofable otherwise.
"""
from __future__ import annotations

import os
import time

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse

from promptlab.models import RateBucket

WINDOW_SECONDS = int(os.getenv("AI_RATE_LIMIT_WINDOW_SECONDS", "60"))
KEEP_WINDOWS = 60  # prune rows older than ~1h of windows


class RateLimitExceeded(Exception):
    """Raised when the per-window quota for a bucket is exhausted."""

    def __init__(self, message: str, *, retry_after: int = WINDOW_SECONDS):
        super().__init__(message)
        self.retry_after = retry_after


def rate_limit_enabled() -> bool:
    return os.getenv("AI_RATE_LIMIT_ENABLED", "True").lower() != "false"


def _limit_for(bucket: str) -> int:
    """Per-bucket quota per window, overridable per bucket via env."""
    specific = os.getenv(f"AI_RATE_LIMIT_{bucket.upper()}_PER_MINUTE")
    if specific:
        try:
            return int(specific)
        except ValueError:
            pass
    try:
        return int(os.getenv("AI_RATE_LIMIT_PER_MINUTE", "12"))
    except ValueError:
        return 12


def client_ip(request) -> str:
    """Real client IP - only honours X-Forwarded-For behind a trusted proxy."""
    if os.getenv("TRUST_PROXY_HEADERS", "False").lower() == "true":
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or "unknown"


def client_key(request) -> str:
    """Stable identity for quota purposes: user > session > IP."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"u:{user.pk}"
    if request.session.session_key:
        return f"s:{request.session.session_key}"
    return f"ip:{client_ip(request)}"


def _prune(now_window: int) -> None:
    RateBucket.objects.filter(window__lt=now_window - KEEP_WINDOWS).delete()


def hit(key: str, window_seconds: int = WINDOW_SECONDS) -> int:
    """Atomically increment and return the count for the current window."""
    now_window = int(time.time() // window_seconds)
    full_key = f"{key}:{now_window}"
    try:
        with transaction.atomic():
            updated = RateBucket.objects.filter(key=full_key).update(count=F("count") + 1)
            if not updated:
                try:
                    RateBucket.objects.create(key=full_key, window=now_window, count=1)
                except IntegrityError:  # lost the race - just bump the row
                    RateBucket.objects.filter(key=full_key).update(count=F("count") + 1)
            count = RateBucket.objects.get(key=full_key).count
    except Exception:  # never let rate limiting break a feature
        import logging
        logging.getLogger("promptlab.ratelimit").warning(
            "Rate limit counter unavailable; allowing request", exc_info=True)
        return 1
    if now_window % 17 == 0:  # occasional cheap cleanup
        try:
            _prune(now_window)
        except Exception:
            pass
    return count


def check_rate_limit(request, bucket: str = "ai") -> None:
    """Raise RateLimitExceeded when this identity has spent its quota."""
    if not rate_limit_enabled():
        return
    limit = _limit_for(bucket)
    if limit <= 0:
        return
    if hit(f"rl:{bucket}:{client_key(request)}") > limit:
        raise RateLimitExceeded(
            f"Rate limit reached ({limit} AI requests per "
            f"{WINDOW_SECONDS // 60 or 1} minute(s)) for your account. "
            f"Please wait a moment and try again.",
            retry_after=WINDOW_SECONDS)


def remaining(request, bucket: str = "ai") -> int:
    """Advisory remaining quota for the current window (never negative)."""
    if not rate_limit_enabled():
        return _limit_for(bucket)
    limit = _limit_for(bucket)
    now_window = int(time.time() // WINDOW_SECONDS)
    row = RateBucket.objects.filter(key=f"rl:{bucket}:{client_key(request)}:{now_window}").first()
    return max(0, limit - (row.count if row else 0))


def reset_rate_limit(request=None, bucket: str = "ai", *, key: str | None = None) -> None:
    """Clear counters - used by tests and by CLI tooling after an incident."""
    if key is None and request is None:
        RateBucket.objects.all().delete()
        return
    ident = key or client_key(request)
    RateBucket.objects.filter(key__startswith=f"rl:{bucket}:{ident}:").delete()


def rate_limited_json_response(exc: RateLimitExceeded) -> JsonResponse:
    response = JsonResponse({"ok": False, "error_code": "rate_limit",
                             "error": str(exc),
                             "retry_after": exc.retry_after}, status=429)
    response["Retry-After"] = str(exc.retry_after)
    return response
