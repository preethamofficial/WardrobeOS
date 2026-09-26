# AI provider strategy

Do not hard-code one vendor.

The project has adapters for:
- Hugging Face
- Gemini
- Local fallback

The provider interface can be expanded to 4–5 providers without changing the Django views.

Use only providers whose current free quota/terms meet your needs. Free tiers can change.
