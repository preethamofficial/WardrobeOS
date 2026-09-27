# AI Smart Wardrobe OS

A local-first, privacy-first AI wardrobe, outfit planner, rotation, laundry and analytics application.

## Core principles
- No paid service is required for the core application.
- External AI providers are optional and isolated behind an AI Orchestrator.
- If an AI provider is unavailable, the local rule engine still works.
- Wardrobe images are stored locally by default.
- The UI is responsive and designed like a modern personal productivity app.

## Quick start on Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## The colour engine (v3)

Colour identification is fully offline and needs no API key. On every photo
upload the pipeline:

1. **Focuses on the garment** - background colours are learned from the photo
   border (hanger, wall, floor) and rejected in perceptual CIELAB space, with
   centre-weighted sampling.
2. **Clusters remaining pixels** with a deterministic, seeded weighted
   k-means and merges perceptually identical clusters.
3. **Names every colour** against a curated ~65-anchor fashion lexicon using
   weighted CIELAB distance: "Navy", "Mustard", "Wine", "Blush Pink",
   "Sage", "Camel"... (never "dark blueish").
4. **Classifies a colour family** (blue, neutral, red, denim...) that drives
   the outfit rules, and **detects the pattern** (solid / two-tone /
   multicolour / patterned).

Every item stores a rich palette `[{hex, name, family, share}]`, an auto
filled `color`, a `color_family`, and a generated web thumbnail. The enhancer
is idempotent (EXIF-tagged) and exposure/contrast correction only fires on
genuinely bad photos, so dark saturated garments keep their identity.

See `docs/COLOR_ENGINE.md` for the full design.

## The outfit engine (v3)

Recommendations blend rotation balance, occasion formality, season, live
weather (Open-Meteo), family-aware colour harmony, pattern-clash detection -
and use **layers** (jackets/hoodies/sweaters), **dresses** and properly
**scored shoes**. Every outfit ships item-specific reasons ("...hasn't been
worn in 6 days", "Colour harmony 92% - classic neutral base").

## Management commands

```powershell
python manage.py reanalyze_wardrobe              # backfill palettes/colours/thumbnails
python manage.py reanalyze_wardrobe --missing-only
python manage.py test                            # run the test suite
```

## Multi-user: every person gets their own wardrobe

The app supports two modes side by side:

- **Local-first mode (default)** - not signed in? You see the shared local
  wardrobe (records with no owner). Perfect for one person on one machine.
- **Account mode** - set `LOGIN_REQUIRED=True` when hosting. Every visitor
  must sign in, and each signed-in user sees **only their own** wardrobe,
  outfits, weekly plans, laundry and trips. Foreign records are invisible
  (404), and ownership is assigned automatically on creation.

Login methods (all free):

- **Email or username + password** - built-in via django-allauth
  (`/accounts/login/`, `/accounts/signup/`).
- **Google Sign-In ("Sign in with Google")** - activate it with two free
  environment variables (`GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`).
  The Google button appears on the login/signup pages automatically once set.
  Setup steps: see `.env.example`. Google OAuth has no cost.
  Authorised redirect URI: `https://YOUR-DOMAIN/accounts/google/login/callback/`
  (locally: `http://127.0.0.1:8000/accounts/google/login/callback/`).

Privacy: Google tokens are never stored (`SOCIALACCOUNT_STORE_TOKENS=False`).
Email verification is off by default so no SMTP account is needed; you can
turn it on later with `ACCOUNT_EMAIL_VERIFICATION` + any free SMTP tier.

## Deploy live for multiple users - $0 options

### Option A: Render (easiest, ~5 minutes)

1. Push this repo to GitHub (see below).
2. On render.com: **New + → Blueprint**, pick your repo - `render.yaml`
   configures a free web service automatically.
3. Render fills in the rest: `SECRET_KEY` is generated for you, `DEBUG=False`,
   `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` point at your service, and
   `migrate` runs on every start (a free instance's disk is wiped on restart,
   so migrating on start is what keeps the app usable).
4. Add anything optional under **Environment** in the dashboard:
   `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` for Google sign-in,
   and/or `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` /
   `HUGGINGFACE_API_KEY` for the AI features.
5. Done - `https://ai-smart-wardrobe-os.onrender.com`.

Two free-tier behaviours to expect:
- **Disk is ephemeral.** Uploaded photos and the SQLite DB are wiped on every
  redeploy and restart. Fine for a demo; use Option B (or a paid disk / Postgres)
  for permanent storage. Pointing `DATABASE_URL` at Postgres preserves your
  records even though photos still need a real disk.
- **The instance sleeps** after ~15 minutes idle, so the first request after a
  pause can take 30-60 seconds while it cold-starts.

If you rename the service, update `CSRF_TRUSTED_ORIGINS` in `render.yaml` to
your new hostname, otherwise form POSTs fail with "CSRF verification failed".

### Option B: PythonAnywhere (free AND persistent disk)

1. Create a free account → **Web** tab → **Add new web app** → Manual config → Python 3.10+.
2. In a Bash console:
   ```bash
   git clone https://github.com/preethamofficial/WardrobeOS.git
   cd WardrobeOS
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate && python manage.py collectstatic --noinput
   python manage.py createsuperuser     # so you can reach /admin/
   ```
3. Web tab → set source directory & WSGI file to point at
   `WardrobeOS/config/wsgi.py`, add
   `/PATH/.venv/lib/python3.x/site-packages` to virtualenv paths.
4. In the same **Web** tab, define the environment variables (this is the
   part people miss - there is no `.env` file on a hosted box):
   `SECRET_KEY` (generate one), `DEBUG=False`,
   `ALLOWED_HOSTS=yourusername.pythonanywhere.com`,
   `CSRF_TRUSTED_ORIGINS=https://yourusername.pythonanywhere.com`,
   `LOGIN_REQUIRED=True`, plus `GOOGLE_OAUTH_CLIENT_ID/SECRET` if you want
   Google sign-in. `FORCE_HTTPS` is implied by `DEBUG=False`.
5. Reload the web app. Your data stays on disk - images and SQLite survive
   restarts and redeploys.

Both have long-standing **free tiers** suitable for hobby use (Render's sleeps
when idle; PythonAnywhere's is always-on with CPU/memory limits), and the app
itself needs no paid service - weather is Open-Meteo, the colour engine is
offline, and Google OAuth is free. Free tiers and their limits are controlled by
those providers and can change, so treat "free" as their current published
terms rather than a guarantee; the source code is MIT-licensed.

## Push to GitHub

```powershell
git init -b main
git add .
git commit -m "AI Smart Wardrobe OS"
git remote add origin https://github.com/preethamofficial/WardrobeOS.git
git push -u origin main
```
`.env`, `db.sqlite3`, `media/`, `staticfiles/` and logs are git-ignored - no
secrets or personal photos get published. Verify with
`git status --ignored` before the first push if you want to be sure, and note
that `.dockerignore` keeps the same files out of Docker images too.

## Optional AI providers

The provider adapters are **fully implemented** (Groq, Gemini, OpenRouter,
Hugging Face, Ollama and an always-on local colour engine) - not placeholders.
Add keys only for the providers you want; the app starts and works fine with
none of them.

The offline colour engine already covers colour, family and pattern detection
with no key at all. Providers additionally fill category / material / formality
from photos, and power the Prompt Lab text features.

Routing is automatic: configured providers are tried in `AI_PROVIDER_ORDER`,
every failure falls through to the next, and the local rule engine is always
the final fallback.

> **Model IDs go stale.** Vendors retire models without warning - Google shut
> down the 2.0 Gemini generation and now access-limits 2.5, Groq moved
> `llama-3.3-70b-versatile` to a paid Enterprise tier, and OpenRouter retires
> `:free` variants often. The defaults in `.env.example` point at currently
> available free models, and Gemini auto-falls-back if its model is retired. If
> an AI feature starts returning an auth/404 error, re-check the model list -
> see `docs/AI_PROVIDERS.md`.

See `.env.example` and `ai/providers/`.

## Included
- Advanced responsive dashboard with today's outfit and wardrobe colour DNA
- Digital wardrobe with search, category/status filters and pagination
- Image upload with idempotent enhancement (EXIF rotation fix, guarded
  exposure/contrast normalization, resize) + automatic thumbnails
- Offline colour identification: naming, family, pattern, palette shares
- Clothing metadata with auto-fill
- Outfit scoring with layers, dresses, scored shoes and pattern logic
- Weather via Open-Meteo (free, keyless)
- Rotation tracking
- Laundry queue
- Weekly planner
- Analytics
- Trip foundation
- AI provider orchestration architecture
- Health endpoint (`/health/`), structured logging, hardened settings
- JSON API (`/api/items/`, `/api/weather/`, `/api/outfits/today/`)
- Docker
