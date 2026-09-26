from PIL import Image

from ai.colors import detect_pattern, extract_palette

from .base import AIProvider, AIResult, ProviderUnavailableError


class LocalProvider(AIProvider):
    """Always-available offline vision + rule engine.

    For clothing images it performs real, fully-offline colour analysis:
    garment-focused palette extraction, fashion-lexicon colour naming and
    pattern detection - no API key, no network. Category/material/formality
    stay the domain of optional external providers (configure one to fill
    them in).
    """

    id = "local"
    label = "Local colour engine"
    capabilities = ("vision",)
    default_model = "colour-engine-v3"
    docs_url = ""

    @classmethod
    def is_configured(cls) -> bool:
        return True

    @classmethod
    def api_key_env(cls) -> str:
        return ""

    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        raise ProviderUnavailableError(
            "The local rule engine cannot generate freeform AI text. "
            "Configure a provider (GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY "
            "or HUGGINGFACE_API_KEY) to use AI-backed features."
        )

    def analyze(self, image_path):
        """Offline garment colour analysis - reliable and deterministic."""
        palette = extract_palette(image_path)
        if not palette:
            return {"confidence": 0.3}
        primary = palette[0]
        return {
            "color": primary.get("name", ""),
            "color_family": primary.get("family", ""),
            "pattern": detect_pattern(palette),
            "palette": palette,
            "confidence": 0.85,
            "engine": "colour-engine-v3",
            "note": "Offline colour analysis - no external AI needed",
        }

