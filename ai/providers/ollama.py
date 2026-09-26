"""Ollama provider - fully local, offline-capable text generation.

Ollama runs open models on your own machine (https://ollama.com), so prompts and
generated text never leave the device: no account, no key, no per-token cost.
That makes it the privacy-first option for Prompt Lab and a good fit for the
"local-first" promise of this project.

Enable it with:

    OLLAMA_ENABLED=True
    OLLAMA_MODEL=llama3.2            # any model you have pulled
    OLLAMA_BASE_URL=http://127.0.0.1:11434

`OLLAMA_BASE_URL` also lets you point at a remote Ollama box on your own network.
"""
from __future__ import annotations

import os

from .base import (AIProvider, AIResult, InvalidResponseError, now_ms,
                   ProviderUnavailableError, post_json)
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _enabled() -> bool:
    return os.getenv("OLLAMA_ENABLED", "False").strip().lower() in ("1", "true", "yes", "on")


class OllamaProvider(AIProvider):
    id = "ollama"
    label = "Ollama (local)"
    capabilities = ("text",)
    default_model = "llama3.2"
    docs_url = "https://ollama.com"

    @classmethod
    def api_key_env(cls) -> str:
        # No credentials exist: enablement is the configuration switch.
        return "OLLAMA_ENABLED"

    @classmethod
    def api_key(cls) -> str:
        return "local" if _enabled() else ""

    @classmethod
    def is_configured(cls) -> bool:
        return _enabled()

    def status(self) -> dict:
        status = super().status()
        status["model"] = self._model()
        status["base_url"] = self._base_url()
        status["key_env"] = "OLLAMA_ENABLED"
        return status

    def _model(self) -> str:
        return os.getenv("OLLAMA_MODEL", self.default_model).strip() or self.default_model

    def _base_url(self) -> str:
        return os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/") or DEFAULT_BASE_URL

    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        started = now_ms()
        payload = {
            "model": model or self._model(),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        try:
            body = post_json(f"{self._base_url()}/api/generate", payload=payload,
                             headers={"Content-Type": "application/json"}, timeout=timeout)
        except ProviderUnavailableError as exc:
            # The usual cause is simply "Ollama is not running", which deserves a
            # clearer message than a generic network error.
            raise ProviderUnavailableError(
                f"Could not reach Ollama at {self._base_url()}. Start it with `ollama serve` "
                f"and make sure `ollama pull {payload['model']}` has been run.") from exc
        text = (body.get("response") or "").strip()
        if not text:
            raise InvalidResponseError("Ollama returned an empty completion")
        usage = {}
        if body.get("prompt_eval_count"):
            usage["prompt_tokens"] = body["prompt_eval_count"]
        if body.get("eval_count"):
            usage["completion_tokens"] = body["eval_count"]
        if usage:
            usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        return AIResult(provider=self.id, model=payload["model"], text=text, ok=True,
                        latency_ms=now_ms() - started, usage=usage)