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
from .ollama import OllamaProvider
from .openrouter import OpenRouterProvider

ALL_PROVIDERS = [
    OllamaProvider,      # fully local, no key, no cost, works offline
    GroqProvider,
    GeminiProvider,
    OpenRouterProvider,
    HuggingFaceProvider,
    LocalProvider,       # last resort: deterministic rule engine, never fake AI
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
             os.getenv("AI_PROVIDER_ORDER", "ollama,groq,gemini,openrouter,huggingface,local").split(",")
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
            error_message=("No AI provider is configured. Enable the free local option by "
                           "installing Ollama (OLLAMA_ENABLED=True), or add GROQ_API_KEY, "
                           "GEMINI_API_KEY, OPENROUTER_API_KEY or HUGGINGFACE_API_KEY to "
                           "your .env file. Local prompt tools still work without a provider."),
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


def provider_catalog(user=None) -> list[dict]:
    """Provider status annotated with a per-user recommendation.

    Shared keys should not be spent on anonymous traffic, so when `user` is not
    signed in hosted providers are reported as available-but-recommendation-off.
    """
    signed_in = bool(user is not None and getattr(user, "is_authenticated", False))
    catalog = []
    for entry in provider_status():
        entry = dict(entry)
        local = entry["id"] == "ollama"
        entry["signed_in"] = signed_in
        entry["recommended"] = bool(entry["configured"] and (local or signed_in))
        if not entry["configured"]:
            entry["hint"] = ("Install Ollama and set OLLAMA_ENABLED=True for free offline AI."
                             if local else
                             f"Add {entry['key_env']} to your .env file to enable this provider.")
        elif local:
            entry["hint"] = "Runs on your own machine - no key, no cost, works offline."
        elif not signed_in:
            entry["hint"] = "Sign in to use this shared provider, or use Ollama for free local AI."
        else:
            entry["hint"] = "Ready to use."
        catalog.append(entry)
    return catalog


__all__ = [
    "AIError", "AIProvider", "AIResult", "AuthError", "InvalidResponseError",
    "MissingConfigError", "ProviderTimeoutError", "ProviderUnavailableError",
    "RateLimitError", "GroqProvider", "GeminiProvider", "OpenRouterProvider",
    "HuggingFaceProvider", "OllamaProvider", "LocalProvider", "provider_order",
    "provider_status", "provider_catalog", "configured_text_providers", "complete_text",
]

