"""Shared plumbing for OpenAI-compatible chat-completions endpoints.

Groq, OpenRouter and the Hugging Face router all expose the same
`POST {base}/chat/completions` shape, so one implementation serves all three.
"""
from __future__ import annotations

from .base import AIProvider, AIResult, InvalidResponseError, now_ms, post_json


class OpenAICompatProvider(AIProvider):
    base_url: str = ""

    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        started = now_ms()
        chosen_model = model or _env_model(self.id, self.default_model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = post_json(
            f"{self.base_url}/chat/completions",
            payload={"model": chosen_model, "messages": messages,
                     "temperature": temperature, "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {self.api_key()}",
                     "Content-Type": "application/json"},
            timeout=timeout,
        )
        choices = body.get("choices") or []
        text = ""
        if choices:
            text = str((choices[0].get("message") or {}).get("content") or "").strip()
        if not text:
            raise InvalidResponseError("provider returned an empty completion")
        usage = body.get("usage") or {}
        return AIResult(
            provider=self.id, model=body.get("model", chosen_model), text=text, ok=True,
            latency_ms=now_ms() - started,
            usage={k: usage.get(k) for k in
                   ("prompt_tokens", "completion_tokens", "total_tokens") if usage.get(k)},
        )


def _env_model(provider_id: str, default: str) -> str:
    import os
    return os.getenv(f"{provider_id.upper()}_MODEL", default).strip() or default
