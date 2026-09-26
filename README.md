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
3. Set env vars in the dashboard: `SECRET_KEY` (auto), `LOGIN_REQUIRED=True`,
   plus `GOOGLE_OAUTH_CLIENT_ID/SECRET` if you want Google sign-in.
4. Done - `https://your-app.onrender.com`.

Free-tier caveat: disk is ephemeral, so uploaded photos/DB reset on redeploys.
Great for a demo; use Option B for persistence.

### Option B: PythonAnywhere (free AND persistent disk)

1. Create a free account → **Web** tab → **Add new web app** → Manual config → Python 3.10+.
2. In a Bash console:
   ```bash
   git clone https://github.com/YOU/AI_Smart_Wardrobe_OS.git
   cd AI_Smart_Wardrobe_OS
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate && python manage.py collectstatic --noinput
   ```
3. Web tab → set source directory & WSGI file to point at
   `AI_Smart_Wardrobe_OS/config/wsgi.py`, add
   `/PATH/.venv/lib/python3.x/site-packages` to virtualenv paths, set your
   env vars (SECRET_KEY, LOGIN_REQUIRED=True, Google keys) in the web tab.
4. Your app stays up with persistent storage - images and SQLite survive.

Both options are free forever for hobby use; the app itself needs no paid
service (weather is Open-Meteo, colour engine is offline, Google OAuth is free).

## Push to GitHub

```powershell
git init -b main
git add .
git commit -m "AI Smart Wardrobe OS"
git remote add origin https://github.com/YOU/AI_Smart_Wardrobe_OS.git
git push -u origin main
```
`.env`, `db.sqlite3`, `media/` and logs are git-ignored - no secrets or
personal photos get published.

## Optional AI providers

Provider adapters are intentionally placeholders. Add keys only for providers
you choose and whose current free quota suits your use. The offline colour
engine already covers colour, family and pattern detection; providers can
additionally fill category / material / formality from photos.

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
