"""AI provider registry: discovery, ordering, status, and text fallback routing.

Adding a new provider = create a subclass of AIProvider (or OpenAICompatProvider)
and append it to ALL_PROVIDERS. Nothing else needs to change.
"""
from __future__ import annotations

import os

from .base import (AIError, AIProvider, AIResult, AuthError, InvalidResponseError,
                   MissingConfigError, ProviderTimeoutError, ProviderUnavailableError,
                   RateLimitError)
from .gemini import GeminiProvider
from .groq import GroqProvider
from .huggingface import HuggingFaceProvider
from .local import LocalProvider
from .openrouter import OpenRouterProvider

ALL_PROVIDERS = [
    GroqProvider,
    GeminiProvider,
    OpenRouterProvider,
    HuggingFaceProvider,
    LocalProvider,
]

_INSTANCES: dict[str, AIProvider] = {}


def _instance(provider_id: str) -> AIProvider | None:
    if not _INSTANCES:
        for cls in ALL_PROVIDERS:
            _INSTANCES[cls.id] = cls()
    return _INSTANCES.get(provider_id)


def provider_order() -> list[str]:
    """Configured-first ordering honouring AI_PROVIDER_ORDER, then auto-discovery."""
    order = [x.strip().lower() for x in
             os.getenv("AI_PROVIDER_ORDER", "groq,gemini,openrouter,huggingface,local").split(",")
             if x.strip()]
    known = [cls.id for cls in ALL_PROVIDERS]
    ordered = [pid for pid in order if pid in known]
    ordered += [pid for pid in known if pid not in ordered]
    # Configured providers (and the local rule engine) first.
    configured = [pid for pid in ordered
                  if pid == "local" or (_instance(pid) or LocalProvider()).is_configured()]
    return configured or ordered


def provider_status() -> list[dict]:
    """One entry per provider for the UI. Never exposes key material."""
    out = []
    for cls in ALL_PROVIDERS:
        inst = _instance(cls.id) or cls()
        out.append(inst.status())
    return out


def configured_text_providers() -> list[AIProvider]:
    out = []
    for pid in provider_order():
        inst = _instance(pid)
        if inst and inst.is_configured() and "text" in inst.capabilities:
            out.append(inst)
    return out


def complete_text(prompt: str, *, system: str | None = None, model: str | None = None,
                  temperature: float = 0.7, max_tokens: int = 1400,
                  timeout: int = 45, providers: list[str] | None = None) -> AIResult:
    """Send one prompt to the first configured provider, falling back on failure.

    Returns the best AIResult (successful, or the last error) and never raises.
    """
    chosen = []
    for pid in (providers or provider_order()):
        inst = _instance(pid)
        if inst and inst.is_configured() and "text" in inst.capabilities:
            chosen.append(inst)
    if not chosen:
        return AIResult(
            provider="none", model="", ok=False, error_code="missing_config",
            error_message=("No AI provider is configured. Add GROQ_API_KEY, GEMINI_API_KEY, "
                           "OPENROUTER_API_KEY or HUGGINGFACE_API_KEY to your .env file. "
                           "Local prompt tools still work without a provider."),
        )

    result = AIResult(provider="none", model="")
    for inst in chosen:
        try:
            candidate = inst.complete(prompt, system=system, model=model, temperature=temperature,
                                      max_tokens=max_tokens, timeout=timeout)
            candidate.attempts = list(result.attempts) + [{
                "provider": inst.id, "ok": True, "error_code": None}]
            return candidate
        except AIError as exc:
            result.attempts = list(result.attempts) + [{
                "provider": inst.id, "ok": False, "error_code": exc.code}]
            result.provider, result.error_code, result.error_message = inst.id, exc.code, exc.user_message
    return result


__all__ = [
    "AIError", "AIProvider", "AIResult", "AuthError", "InvalidResponseError",
    "MissingConfigError", "ProviderTimeoutError", "ProviderUnavailableError",
    "RateLimitError", "GroqProvider", "GeminiProvider", "OpenRouterProvider",
    "HuggingFaceProvider", "LocalProvider", "provider_order", "provider_status",
    "configured_text_providers", "complete_text",
]

