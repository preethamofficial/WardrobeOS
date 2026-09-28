from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
BASE_DIR=Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR/".env")

# Every setting below reads `DJANGO_<NAME>` first, then plain `<NAME>`, then a
# default. The DJANGO_-prefixed form is the convention on Render/Docker, so a
# platform that auto-injects `DJANGO_SECRET_KEY` works without extra config, and
# the short names in .env keep local development readable.
def env(name, default=""):
    return os.getenv(f"DJANGO_{name}", os.getenv(name, default))

def flag(name, default=False):
    """Parse a boolean env var leniently (true/1/yes/on vs false/0/no/off)."""
    raw = env(name, "True" if default else "False").strip().lower()
    return raw in ("1", "true", "yes", "on")

DEBUG=env("DEBUG","True").strip().lower() in ("1","true","yes","on")
# Fail safely: never ship the "dev-secret" placeholder to production. With
# DEBUG=False a missing/blank SECRET_KEY aborts startup instead of silently
# signing sessions with a value that is public in this repository.
SECRET_KEY=env("SECRET_KEY","").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "SECRET_KEY is required when DEBUG=False. Generate one with "
            "`python -c \"import secrets;print(secrets.token_urlsafe(64))\"` "
            "and set it as an environment variable (see .env.example).")
    SECRET_KEY="dev-secret"
elif SECRET_KEY in ("change-this-in-production","dev-secret") and not DEBUG:
    # A copied .env.example must never end up signing real production sessions.
    raise ImproperlyConfigured(
        "SECRET_KEY is still the .env.example placeholder. Generate a real one "
        "with `python -c \"import secrets;print(secrets.token_urlsafe(64))\"`.")
ALLOWED_HOSTS=[x.strip() for x in env("ALLOWED_HOSTS","127.0.0.1,localhost").split(",") if x.strip()]
if os.getenv("RENDER_EXTERNAL_HOSTNAME"): ALLOWED_HOSTS.append(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
CSRF_TRUSTED_ORIGINS=[x.strip() for x in env("CSRF_TRUSTED_ORIGINS","").split(",") if x.strip()]
INSTALLED_APPS=[
"django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions",
"django.contrib.messages","django.contrib.staticfiles","django.contrib.sites",
"accounts_app","wardrobe","outfits","planner","laundry",
"analytics_app","trips","promptlab","styleos",
"allauth","allauth.account","allauth.socialaccount"]
# Google Sign-In activates automatically when OAuth keys are configured (free).
_GOOGLE_CLIENT_ID=os.getenv("GOOGLE_OAUTH_CLIENT_ID","").strip()
_GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET","").strip()
SOCIALACCOUNT_PROVIDERS={}
if _GOOGLE_CLIENT_ID and _GOOGLE_CLIENT_SECRET:
    INSTALLED_APPS.append("allauth.socialaccount.providers.google")
    SOCIALACCOUNT_PROVIDERS["google"]={
        "APP":{"client_id":_GOOGLE_CLIENT_ID,"secret":_GOOGLE_CLIENT_SECRET,"key":""},
        "SCOPE":["profile","email"],
        "AUTH_PARAMS":{"access_type":"online"},
        "OAUTH_PKCE_ENABLED":True}
MIDDLEWARE=[
"django.middleware.security.SecurityMiddleware","whitenoise.middleware.WhiteNoiseMiddleware",
"django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware",
"django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware",
"django.contrib.messages.middleware.MessageMiddleware",
"django.middleware.clickjacking.XFrameOptionsMiddleware",
"allauth.account.middleware.AccountMiddleware",
"config.middleware.LoginRequiredMiddleware"]
AUTHENTICATION_BACKENDS=[
"django.contrib.auth.backends.ModelBackend",
"allauth.account.auth_backends.AuthenticationBackend"]
SITE_ID=1
LOGIN_REDIRECT_URL=env("LOGIN_REDIRECT_URL","/")
LOGOUT_REDIRECT_URL="/"
# Email-first authentication. Verification is mandatory for password accounts;
# hosted deployments must provide SMTP so verification and recovery emails reach users.
# Authentication is email-first: usernames remain an internal Django identifier,
# but users can no longer sign in with a username. Every password account must
# provide and verify a unique email address before access is granted.
ACCOUNT_USER_MODEL_USERNAME_FIELD=None
ACCOUNT_LOGIN_METHODS={"email"}
ACCOUNT_SIGNUP_FIELDS=["email*","password1*","password2*"]
ACCOUNT_EMAIL_VERIFICATION="mandatory"
ACCOUNT_UNIQUE_EMAIL=True
ACCOUNT_PREVENT_ENUMERATION=True
ACCOUNT_LOGIN_ON_PASSWORD_RESET=False
ACCOUNT_CONFIRM_EMAIL_ON_GET=True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=3
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE=True
SOCIALACCOUNT_STORE_TOKENS=False  # privacy-first: never store Google tokens
# SMTP (optional). Any provider works; Gmail needs an App Password, and free
# tiers such as Brevo/Resend/Mailgun SMTP also work. Left unset -> console email.
EMAIL_HOST=env("EMAIL_HOST","").strip()
EMAIL_HOST_USER=env("EMAIL_HOST_USER","").strip()
EMAIL_HOST_PASSWORD=env("EMAIL_HOST_PASSWORD","").strip()
EMAIL_PORT=int(env("EMAIL_PORT","587"))
EMAIL_USE_TLS=flag("EMAIL_USE_TLS",True)
DEFAULT_FROM_EMAIL=env("DEFAULT_FROM_EMAIL") or (EMAIL_HOST_USER or "wardrobeos@localhost")
if EMAIL_HOST:
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend"
LOGIN_REQUIRED=flag("LOGIN_REQUIRED")
# HTTPS hardening. Both Render and PythonAnywhere terminate TLS at their proxy and
# forward X-Forwarded-Proto, so trusting that header is required for
# request.is_secure() to be correct. `FORCE_HTTPS=True` turns on the full set of
# transport guarantees (HSTS, secure cookies, HTTP->HTTPS redirect) and is implied
# by DEBUG=False in production. Left off by default so plain-HTTP local dev and
# health checks keep working.
SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")
_FORCE_HTTPS=flag("FORCE_HTTPS", not DEBUG)
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/"templates"],
"APP_DIRS":True,"OPTIONS":{"context_processors":[
"django.template.context_processors.request","django.contrib.auth.context_processors.auth",
"django.contrib.messages.context_processors.messages","config.context_processors.weather",
"config.context_processors.auth_flags"]}}]
WSGI_APPLICATION="config.wsgi.application"
_db_url=env("DATABASE_URL")
DATABASES={"default":dj_database_url.parse(_db_url,conn_max_age=600)} if _db_url else \
{"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS=[
{"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
{"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":8}},
{"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},
{"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE="en-us"; TIME_ZONE="Asia/Kolkata"; USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"; STATICFILES_DIRS=[BASE_DIR/"static"]; STATIC_ROOT=BASE_DIR/"staticfiles"
STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
"staticfiles":{"BACKEND":"whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG
else "django.contrib.staticfiles.storage.StaticFilesStorage"}}
MEDIA_URL="/media/"; MEDIA_ROOT=env("MEDIA_ROOT",str(BASE_DIR/"media"))
# Serve uploads through wardrobe.media_views.serve_media (ownership-checked) in
# every environment; see config/urls.py. MEDIA_ROOT must be a persistent volume
# in production, otherwise photos vanish on redeploy.
# Optional shared cache (rate limiting uses the database by default, so this is
# only useful for other caching); needs `pip install redis` when set.
_REDIS_URL=env("REDIS_URL","").strip()
if _REDIS_URL:
    CACHES={"default":{"BACKEND":"django.core.cache.backends.redis.RedisCache",
                       "LOCATION":_REDIS_URL}}
else:
    # Short-lived per-process cache for external read paths such as weather.
    CACHES={"default":{"BACKEND":"django.core.cache.backends.locmem.LocMemCache",
                       "LOCATION":"wardrobeos-default"}}
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
X_FRAME_OPTIONS="DENY"; SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_SAMESITE="Lax"; CSRF_COOKIE_SAMESITE="Lax"
SESSION_COOKIE_AGE=int(env("SESSION_COOKIE_AGE","1209600"))
DATA_UPLOAD_MAX_MEMORY_SIZE=int(env("DATA_UPLOAD_MAX_MEMORY_SIZE",str(12*1024*1024)))
LOG_LEVEL=env("LOG_LEVEL","INFO")
LOGGING={"version":1,"disable_existing_loggers":False,
"formatters":{"std":{"format":"%(asctime)s %(levelname)-7s %(name)s: %(message)s"}},
"handlers":{"console":{"class":"logging.StreamHandler","formatter":"std"}},
"root":{"handlers":["console"],"level":LOG_LEVEL},
"loggers":{"django":{"level":"INFO"},"wardrobe":{"level":"INFO","propagate":True},
"ai":{"level":"INFO","propagate":True}}}
# Transport security, applied once. `_FORCE_HTTPS` is implied by DEBUG=False so a
# production deploy is hardened without anyone remembering an extra variable.
if _FORCE_HTTPS:
    SECURE_SSL_REDIRECT=True
    SESSION_COOKIE_SECURE=True
    CSRF_COOKIE_SECURE=True
    SECURE_HSTS_SECONDS=int(env("SECURE_HSTS_SECONDS","31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True
    # Preload is deliberately off: it is effectively irreversible for a domain
    # (hard to undo in browsers) so it stays an explicit per-domain opt-in.
    SECURE_HSTS_PRELOAD=flag("SECURE_HSTS_PRELOAD")
