"""OpenRouter text provider (OpenAI-compatible, many models have a :free tier).

Keys are optional and read from OPENROUTER_API_KEY. Model override: OPENROUTER_MODEL.

Free-tier note: OpenRouter retires `:free` variants often. The old default,
`meta-llama/llama-3.3-70b-instruct:free`, is **no longer served** (the paid
`meta-llama/llama-3.3-70b-instruct` still exists, but costs tokens). The default
below is a currently-listed free model so a new key works immediately. To pick
another, list the live ones with: https://openrouter.ai/api/v1/models
and look for the `:free` suffix.
"""
from .openai_compat import OpenAICompatProvider


class OpenRouterProvider(OpenAICompatProvider):
    id = "openrouter"
    label = "OpenRouter"
    capabilities = ("text",)
    base_url = "https://openrouter.ai/api/v1"
    default_model = "qwen/qwen3.8-27b:free"
    docs_url = "https://openrouter.ai/models"
