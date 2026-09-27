# AI provider strategy

Do not hard-code one vendor.

The provider interface in `ai/providers/base.py` is small on purpose (a
`complete()` method plus a `status()` descriptor), so a new vendor is one
subclass and one line in `ALL_PROVIDERS` in `ai/providers/__init__.py`.
Nothing in the Django views changes.

## Adapters that ship today

| Provider | Env key | Capabilities | Default model | Notes |
|---|---|---|---|---|
| Ollama | `OLLAMA_ENABLED` | text | `llama3.2` | Fully local, no key, no cost, works offline. Local dev only. |
| Groq | `GROQ_API_KEY` | text | `openai/gpt-oss-20b` | Free developer tier. |
| Gemini | `GEMINI_API_KEY` | text + **vision** | `gemini-3.5-flash` | Free tier; the only vision provider with a generous free quota. |
| OpenRouter | `OPENROUTER_API_KEY` | text | `qwen/qwen3.8-27b:free` | Many models have a `:free` variant. |
| Hugging Face | `HUGGINGFACE_API_KEY` (or `HF_TOKEN`) | text + **vision** | `meta-llama/Llama-3.1-8B-Instruct` | Router chat + ViT image classification. |
| Local colour engine | *(none)* | vision | `colour-engine-v3` | Always on, offline, deterministic. Last-resort fallback. |

## How routing works

- `provider_order()` puts every *configured* provider first, then the rest.
  `AI_PROVIDER_ORDER` sets the preference order.
- `complete_text()` tries each in turn and falls back on failure, returning the
  best result rather than raising.
- The **local colour engine is always available** and is never disabled. Colour,
  colour family and pattern detection need no API key at all; providers only add
  category / material / formality inference from photos and the Prompt Lab text
  features.
- Provider status is exposed to the UI without ever leaking key material.

## Model IDs drift - check them periodically

Vendors retire model IDs without notice, which breaks a hard-coded default:

- **Google** shut down the entire 2.0 generation and now *access-limits* the
  2.5 generation to projects that used it before the restriction, so a new API
  key gets 403/404 on 2.5 IDs. See the deprecations table.
- **Groq** moved `llama-3.3-70b-versatile` to the Enterprise tier, so it is no
  longer reachable on the free plan.
- **OpenRouter** retires `:free` variants frequently.

`GeminiProvider` defends against this by walking `FALLBACK_MODELS` when the API
reports the model as missing, so a retirement degrades to a slower call rather
than an outage. The other providers do not - re-check their model pages when an
AI feature starts returning an auth/404 error:

- https://ai.google.dev/gemini-api/docs/deprecations
- https://console.groq.com/docs/models
- https://openrouter.ai/api/v1/models
- https://huggingface.co/docs/inference-providers

Use only providers whose current free quota/terms meet your needs. Free tiers
can change at any time.
