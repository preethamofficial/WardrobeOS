"""Groq text provider (OpenAI-compatible API, free developer tier).

Keys are optional and read from GROQ_API_KEY. Model override: GROQ_MODEL.

Model choice note: `llama-3.3-70b-versatile` is still listed on Groq's model
page, but it has moved to the **Enterprise** tier ("Contact Sales" rate
limits) and is no longer reachable on the free developer plan. The default
below is an open-weight model that is currently served on the free tier, so a
new account works out of the box. Check https://console.groq.com/docs/models
before changing it - Groq deprecates model IDs fairly aggressively.
"""
from .openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    id = "groq"
    label = "Groq"
    capabilities = ("text",)
    base_url = "https://api.groq.com/openai/v1"
    default_model = "openai/gpt-oss-20b"
    docs_url = "https://console.groq.com/docs/models"
