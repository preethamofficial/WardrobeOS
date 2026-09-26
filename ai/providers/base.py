"""Provider-agnostic AI abstraction layer.

Every provider implements the same small surface so the application can route
work to any configured provider and fall back gracefully. Design rules:

- API keys only ever come from environment variables, never code.
- A provider without credentials is simply "not configured" and is skipped.
- All network failures map onto a small, human-readable error taxonomy.
- The local rule engine is always available last; it never fakes model output.
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import requests


class AIError(Exception):
    """Base class for every provider failure with a user-safe message."""

    code = "ai_error"
    user_message = "The AI request failed. Please try again."

    def __init__(self, message: str = "", user_message: str | None = None):
        super().__init__(message or self.user_message)
        if user_message:
            self.user_message = user_message


class MissingConfigError(AIError):
    code = "missing_config"
    user_message = "This provider is not configured. Add its API key to your .env file."


class AuthError(AIError):
    code = "auth_error"
    user_message = "The API key was rejected by the provider. Check the key in your .env file."


class RateLimitError(AIError):
    code = "rate_limit"
    user_message = "The provider rate limit was reached. Wait a moment and try again."


class ProviderTimeoutError(AIError):
    code = "timeout"
    user_message = "The provider took too long to respond. Try again or pick another provider."


class ProviderUnavailableError(AIError):
    code = "unavailable"
    user_message = "The provider is temporarily unavailable. Try another provider."


class InvalidResponseError(AIError):
    code = "invalid_response"
    user_message = "The provider returned an unexpected response."


@dataclass
class AIResult:
    """Normalised outcome of one provider call (success or failure)."""

    provider: str
    model: str
    text: str = ""
    ok: bool = False
    error_code: str | None = None
    error_message: str = ""
    latency_ms: int = 0
    usage: dict = field(default_factory=dict)
    attempts: list = field(default_factory=list)

    @property
    def error(self) -> str:
        return self.error_message or (self.user_message if hasattr(self, "user_message") else "")


class AIProvider(ABC):
    """Common contract for every AI provider adapter."""

    id: str = "base"
    label: str = "Base"
    capabilities: tuple = ("text",)          # subset of {"text", "vision"}
    default_model: str = ""
    docs_url: str = ""

    # -- introspection ----------------------------------------------------
    @classmethod
    def api_key_env(cls) -> str:
        return f"{cls.id.upper()}_API_KEY"

    @classmethod
    def api_key(cls) -> str:
        return os.getenv(cls.api_key_env(), "").strip()

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.api_key())

    def status(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "capabilities": list(self.capabilities),
            "model": os.getenv(f"{self.id.upper()}_MODEL", self.default_model),
            "configured": self.is_configured(),
            "key_env": self.api_key_env(),
            "docs_url": self.docs_url,
        }

    # -- text generation ----------------------------------------------------
    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        """Generate text. Raises AIError subclasses on failure."""


def post_json(url: str, *, payload: dict, headers: dict, timeout: int) -> dict:
    """POST JSON with the shared error taxonomy. Returns parsed JSON."""
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout as exc:
        raise ProviderTimeoutError(f"timeout after {timeout}s: {exc}") from exc
    except requests.exceptions.ConnectionError as exc:
        raise ProviderUnavailableError(f"connection failed: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise ProviderUnavailableError(f"network error: {exc}") from exc

    if response.status_code in (401, 403):
        raise AuthError(f"HTTP {response.status_code} from {url}")
    if response.status_code == 429:
        raise RateLimitError("HTTP 429 from provider")
    if response.status_code >= 500:
        raise ProviderUnavailableError(f"HTTP {response.status_code} from provider")
    if response.status_code == 404:
        raise InvalidResponseError(f"model or endpoint not found (HTTP 404): {url}")
    if response.status_code >= 400:
        raise InvalidResponseError(f"HTTP {response.status_code}: {response.text[:200]}")
    try:
        return response.json()
    except ValueError as exc:
        raise InvalidResponseError("provider returned non-JSON body") from exc


def now_ms() -> int:
    return int(time.time() * 1000)
