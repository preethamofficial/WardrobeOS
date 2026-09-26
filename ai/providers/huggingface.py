"""Hugging Face provider: image classification (wardrobe tagging) + router chat.

Keys are optional and read from HUGGINGFACE_API_KEY or HF_TOKEN.
Free-tier availability can change; see https://huggingface.co/docs/inference-providers.
"""
import os

import requests
from PIL import Image

from .base import AIProvider, AIResult, InvalidResponseError, now_ms, post_json

# Image classification model served on the HF Inference API (free tier with a token).
MODEL = "google/vit-base-patch16-224"
ROUTER_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}"
LEGACY_URL = f"https://api-inference.huggingface.co/models/{MODEL}"
CHAT_URL = "https://router.huggingface.co/v1/chat/completions"

# ImageNet-1k label -> wardrobe category
LABEL_TO_CATEGORY = {
    "jersey": "tshirt", "t-shirt": "tshirt", "sweatshirt": "hoodie", "cardigan": "sweater",
    "poncho": "sweater", "wool": "sweater", "abaya": "dress", "gown": "dress",
    "kimono": "dress", "jean": "jeans", "miniskirt": "skirt", "suit": "shirt",
    "running shoe": "shoes", "sandal": "shoes", "loafer": "shoes", "cowboy boot": "shoes",
    "ski boot": "shoes", "bikini": "other", "swimming trunks": "shorts", "pajama": "other",
    "diaper": "other", "apron": "other", "sunglass": "accessory", "sunglasses": "accessory",
    "sombrero": "accessory", "shower cap": "accessory", "crash helmet": "accessory",
    "shield": "accessory", "backpack": "accessory", "wallet": "accessory", "purse": "accessory",
    "handkerchief": "accessory", "scarf": "accessory", "umbrella": "accessory",
}

CATEGORY_TO_FORMALITY = {
    "shirt": "smart_casual", "tshirt": "casual", "pant": "smart_casual", "jeans": "casual",
    "shorts": "casual", "jacket": "smart_casual", "hoodie": "casual", "sweater": "smart_casual",
    "dress": "smart_casual", "skirt": "smart_casual", "shoes": "casual", "accessory": "casual",
    "other": "casual",
}

LABEL_TO_MATERIAL = {
    "jean": "denim", "denim": "denim", "wool": "wool", "velvet": "velvet",
    "leather": "leather", "silk": "silk", "jersey": "cotton", "sweatshirt": "fleece",
}

# Simple palette for average-color detection
PALETTE = [
    ("black", (15, 15, 15)), ("white", (245, 245, 245)), ("grey", (128, 128, 128)),
    ("red", (200, 40, 40)), ("maroon", (128, 0, 32)), ("orange", (235, 140, 30)),
    ("yellow", (240, 220, 60)), ("green", (60, 160, 60)), ("teal", (40, 150, 150)),
    ("blue", (50, 80, 200)), ("navy", (25, 35, 90)), ("purple", (130, 60, 170)),
    ("pink", (235, 130, 170)), ("brown", (120, 75, 40)), ("beige", (225, 200, 160)),
]


def _detect_color(image_path):
    """Average-color fallback so HF results always include a usable color."""
    with Image.open(image_path) as im:
        im = im.convert("RGB").resize((32, 32))
        pixels = list(im.getdata())
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)
    return min(PALETTE, key=lambda item: (item[1][0] - r) ** 2 + (item[1][1] - g) ** 2 + (item[1][2] - b) ** 2)[0]


class HuggingFaceProvider(AIProvider):
    """Hugging Face adapter: router chat-completions for text, inference API for images."""

    id = "huggingface"
    label = "Hugging Face"
    capabilities = ("text", "vision")
    default_model = "meta-llama/Llama-3.1-8B-Instruct"
    docs_url = "https://huggingface.co/docs/inference-providers"

    @classmethod
    def api_key(cls) -> str:
        return (os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN") or "").strip()

    # -- text ---------------------------------------------------------------
    def complete(self, prompt: str, *, system: str | None = None, model: str | None = None,
                 temperature: float = 0.7, max_tokens: int = 1400,
                 timeout: int = 45) -> AIResult:
        started = now_ms()
        chosen_model = model or os.getenv("HUGGINGFACE_MODEL", self.default_model).strip() or self.default_model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = post_json(
            CHAT_URL,
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
        return AIResult(provider=self.id, model=body.get("model", chosen_model), text=text, ok=True,
                        latency_ms=now_ms() - started,
                        usage={k: usage.get(k) for k in
                               ("prompt_tokens", "completion_tokens", "total_tokens") if usage.get(k)})

    # -- vision (clothing analysis, original interface preserved) -----------
    def analyze(self, image_path):
        token = self.api_key()
        if not token:
            return None
        with open(image_path, "rb") as f:
            data = f.read()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}
        labels = None
        for url in (ROUTER_URL, LEGACY_URL):
            try:
                r = requests.post(url, headers=headers, data=data, timeout=30)
                if r.status_code == 503:  # model still loading
                    return None
                r.raise_for_status()
                labels = r.json()
                break
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    continue  # try legacy endpoint
                raise
        if not labels:
            return None
        top = max(labels, key=lambda x: x.get("score", 0))
        label = str(top.get("label", "")).strip().lower()
        score = float(top.get("score", 0))
        if not label or score < 0.25:
            return None

        category = LABEL_TO_CATEGORY.get(label, "other")
        result = {
            "category": category,
            "color": _detect_color(image_path),
            "pattern": "solid",
            "material": LABEL_TO_MATERIAL.get(label, ""),
            "formality": CATEGORY_TO_FORMALITY.get(category, "casual"),
            # ViT top-1 scores run high; clamp so the orchestrator treats it realistically.
            "confidence": max(0.5, min(0.9, score)),
        }
        return result
