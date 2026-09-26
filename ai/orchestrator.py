"""AI orchestration: clothing image analysis + text completion with fallback.

Backward-compatible: `analyze_clothing(image_path)` keeps its original contract
(best-effort dict with a "provider" key). Text routing goes through the
provider registry so new providers are picked up automatically.
"""
from __future__ import annotations

from ai.providers import complete_text, provider_order, provider_status  # noqa: F401
from ai.providers import _instance


def analyze_clothing(image_path):
    """Analyse a clothing photo, trying configured vision providers in order."""
    results = []
    last_error = None
    for pid in provider_order():
        provider = _instance(pid)
        if not provider or "vision" not in provider.capabilities:
            continue
        try:
            if not provider.is_configured() and pid != "local":
                continue
            result = provider.analyze(image_path)
        except Exception as exc:  # provider failure must never break an upload
            last_error = exc
            continue
        if not result:
            continue
        confidence = result.get("confidence", 0)
        if confidence >= 0.70:
            result["provider"] = pid
            return result
        results.append((pid, result))
    if results:
        name, result = max(results, key=lambda x: x[1].get("confidence", 0))
        result["provider"] = name
        return result
    fallback = {"provider": "local", "confidence": 0.35}
    if last_error is not None:
        fallback["note"] = "a vision provider failed; using local fallback"
    return fallback


def run_text(prompt, *, system=None, model=None, temperature=0.7, max_tokens=1400,
             timeout=45, providers=None):
    """Convenience wrapper around the registry's complete_text."""
    return complete_text(prompt, system=system, model=model, temperature=temperature,
                         max_tokens=max_tokens, timeout=timeout, providers=providers)

