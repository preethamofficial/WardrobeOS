from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
BASE_DIR=Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR/".env")
SECRET_KEY=os.getenv("SECRET_KEY","dev-secret")
DEBUG=os.getenv("DEBUG","True").lower()=="true"
ALLOWED_HOSTS=[x.strip() for x in os.getenv("ALLOWED_HOSTS","127.0.0.1,localhost").split(",") if x.strip()]
if os.getenv("RENDER_EXTERNAL_HOSTNAME"): ALLOWED_HOSTS.append(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
CSRF_TRUSTED_ORIGINS=[x.strip() for x in os.getenv("CSRF_TRUSTED_ORIGINS","").split(",") if x.strip()]
INSTALLED_APPS=[
"django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions",
"django.contrib.messages","django.contrib.staticfiles","django.contrib.sites",
"wardrobe","outfits","planner","laundry",
"analytics_app","trips","promptlab",
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
"allauth.account.middleware.AccountMiddleware",
"config.middleware.LoginRequiredMiddleware"]
AUTHENTICATION_BACKENDS=[
"django.contrib.auth.backends.ModelBackend",
"allauth.account.auth_backends.AuthenticationBackend"]
SITE_ID=1
LOGIN_REDIRECT_URL=os.getenv("LOGIN_REDIRECT_URL","/")
LOGOUT_REDIRECT_URL="/"
# Email (and username) login + open signup. Email verification stays off so no
# SMTP account is needed for a free deployment - set to "mandatory" and add
# EMAIL_* vars later if you want verified emails.
ACCOUNT_LOGIN_METHODS={"username","email"}
ACCOUNT_SIGNUP_FIELDS=["username*","email","password1*","password2*"]
ACCOUNT_EMAIL_VERIFICATION="none"
ACCOUNT_UNIQUE_EMAIL=True
SOCIALACCOUNT_STORE_TOKENS=False  # privacy-first: never store Google tokens
LOGIN_REQUIRED=os.getenv("LOGIN_REQUIRED","False").lower()=="true"
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/"templates"],
"APP_DIRS":True,"OPTIONS":{"context_processors":[
"django.template.context_processors.request","django.contrib.auth.context_processors.auth",
"django.contrib.messages.context_processors.messages","config.context_processors.weather",
"config.context_processors.auth_flags"]}}]
WSGI_APPLICATION="config.wsgi.application"
_db_url=os.getenv("DATABASE_URL")
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
MEDIA_URL="/media/"; MEDIA_ROOT=os.getenv("MEDIA_ROOT",str(BASE_DIR/"media"))
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO","https")
X_FRAME_OPTIONS="DENY"; SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_SAMESITE="Lax"; CSRF_COOKIE_SAMESITE="Lax"
SESSION_COOKIE_AGE=int(os.getenv("SESSION_COOKIE_AGE","1209600"))
DATA_UPLOAD_MAX_MEMORY_SIZE=int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE",str(12*1024*1024)))
LOG_LEVEL=os.getenv("LOG_LEVEL","INFO")
LOGGING={"version":1,"disable_existing_loggers":False,
"formatters":{"std":{"format":"%(asctime)s %(levelname)-7s %(name)s: %(message)s"}},
"handlers":{"console":{"class":"logging.StreamHandler","formatter":"std"}},
"root":{"handlers":["console"],"level":LOG_LEVEL},
"loggers":{"django":{"level":"INFO"},"wardrobe":{"level":"INFO","propagate":True},
"ai":{"level":"INFO","propagate":True}}}
if not DEBUG:
    SECURE_SSL_REDIRECT=True; SECURE_HSTS_SECONDS=31536000; SECURE_HSTS_INCLUDE_SUBDOMAINS=True
    SESSION_COOKIE_SECURE=True; CSRF_COOKIE_SECURE=True
