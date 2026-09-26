"""Groq text provider (free tier, Llama/DeepSeek/Qwen models via OpenAI-compatible API).

Free-tier availability can change; keys are optional and read from GROQ_API_KEY.
Model override: GROQ_MODEL (default llama-3.3-70b-versatile).
"""
from .openai_compat import OpenAICompatProvider


class GroqProvider(OpenAICompatProvider):
    id = "groq"
    label = "Groq"
    capabilities = ("text",)
    base_url = "https://api.groq.com/openai/v1"
    default_model = "llama-3.3-70b-versatile"
    docs_url = "https://console.groq.com/docs"
