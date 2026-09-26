"""OpenRouter text provider (freemium: many models offer a :free variant).

Keys are optional and read from OPENROUTER_API_KEY.
Model override: OPENROUTER_MODEL (default a free-tier Llama instruct model).
"""
from .openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    id = "openrouter"
    label = "OpenRouter"
    capabilities = ("text",)
    base_url = "https://openrouter.ai/api/v1"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"
    docs_url = "https://openrouter.ai/docs"

    def complete(self, prompt: str, *, system=None, model=None, temperature=0.7,
                 max_tokens=1400, timeout=45):
        result = super().complete(prompt, system=system, model=model, temperature=temperature,
                                  max_tokens=max_tokens, timeout=timeout)
        return result
