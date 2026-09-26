"""Google Gemini provider (free tier) - text generation + clothing image analysis.

Keys are optional and read from GEMINI_API_KEY. Model override: GEMINI_MODEL.
"""
import os
import base64
import json

from .base import AIProvider, AIResult, InvalidResponseError, now_ms, post_json

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

VALID_CATEGORIES = {"shirt", "tshirt", "pant", "jeans", "shorts", "jacket",
                    "hoodie", "sweater", "dress", "skirt", "shoes", "accessory", "other"}
VALID_FORMALITY = {"formal", "smart_casual", "casual", "sport"}

PROMPT = (
    "Analyze this clothing item photo. Respond with ONLY a JSON object (no markdown fences) with keys: "
    'category (one of "shirt","tshirt","pant","jeans","shorts","jacket","hoodie","sweater","dress",'
    '"skirt","shoes","accessory","other"), '
    'color (plain English color name, e.g. "navy","red","white"), '
    'pattern (e.g. "solid","striped","floral","checked","printed"; use "solid" if unsure), '
    'material (best guess e.g. "cotton","denim","leather", empty string if unsure), '
    'formality (one of "formal","smart_casual","casual","sport"), '
    "confidence (float between 0 and 1)."
)

MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
              ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp"}


class GeminiProvider(AIProvider):
    id = "gemini"
    label = "Google Gemini"
    capabilities = ("text", "vision")
    default_model = "gemini-2.0-flash"
    docs_url = "https://ai.google.dev/gemini-api/docs"

    def _model(self) -> str:
        return os.getenv("GEMINI_MODEL", self.default_model).strip() or self.default_model

    def _generate(self, payload: dict, timeout: int) -> dict:
        return post_json(
            API_URL.format(model=self._model()),
            payload=payload,
            headers={"x-goog-api-key": self.api_key(), "Content-Type": "application/json"},
            timeout=timeout,
        )

    @staticmethod
    def _text_from_body(body: dict) -> str:
        return "".join(
            part.get("text", "")
            for candidate in body.get("candidates", [])
            for part in candidate.get("content", {}).get("parts", [])
        ).strip()

    # -- text ---------------------------------------------------------------
    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        started = now_ms()
        parts = [{"text": prompt}]
        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        body = self._generate(payload, timeout)
        text = self._text_from_body(body)
        if not text:
            raise InvalidResponseError("provider returned an empty completion")
        usage_raw = body.get("usageMetadata") or {}
        usage = {k: usage_raw.get(k) for k in
                 ("promptTokenCount", "candidatesTokenCount", "totalTokenCount") if usage_raw.get(k)}
        return AIResult(provider=self.id, model=model or self._model(), text=text, ok=True,
                        latency_ms=now_ms() - started, usage=usage)

    # -- vision (clothing analysis, original interface preserved) -----------
    def analyze(self, image_path):
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = MIME_TYPES.get(ext, "image/jpeg")
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        payload = {
            "contents": [{"parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": mime_type, "data": data}},
            ]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300},
        }
        body = self._generate(payload, timeout=30)
        text = self._text_from_body(body)
        if not text:
            return None
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return None
        parsed = json.loads(text[start:end + 1])

        result = {}
        category = str(parsed.get("category", "")).lower().strip()
        if category in VALID_CATEGORIES:
            result["category"] = category
        formality = str(parsed.get("formality", "")).lower().strip()
        if formality in VALID_FORMALITY:
            result["formality"] = formality
        for field in ("color", "pattern", "material"):
            value = str(parsed.get(field, "")).strip()
            if value:
                result[field] = value
        try:
            confidence = float(parsed.get("confidence", 0.75))
        except (TypeError, ValueError):
            confidence = 0.75
        result["confidence"] = max(0.0, min(1.0, confidence))
        return result

