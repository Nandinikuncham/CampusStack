"""Environment-driven Django settings for CampusStack."""
import os
import secrets
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = BASE_DIR.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in {"1", "true", "yes"}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set whenever DJANGO_DEBUG is False."
        )
    SECRET_KEY = secrets.token_urlsafe(50)
allowed_hosts_setting = os.environ.get("DJANGO_ALLOWED_HOSTS")
if allowed_hosts_setting is None and DEBUG:
    allowed_hosts_setting = "localhost,127.0.0.1"
allowed_host_values = allowed_hosts_setting.split(",") if allowed_hosts_setting else []
ALLOWED_HOSTS = [host.strip() for host in allowed_host_values if host.strip()]
if not DEBUG and (
    not allowed_hosts_setting
    or not allowed_hosts_setting.strip()
    or any(not host.strip() or "*" in host for host in allowed_host_values)
):
    raise ImproperlyConfigured(
        "In production, DJANGO_ALLOWED_HOSTS must be explicitly set to exact "
        "hostnames; wildcard values are not allowed."
    )
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if any("*" in origin for origin in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS must list explicit frontend origins; wildcards are not allowed."
    )

if not DEBUG:
    missing_production_settings = []
    if not SECRET_KEY:
        missing_production_settings.append("DJANGO_SECRET_KEY")
    if not CSRF_TRUSTED_ORIGINS:
        missing_production_settings.append("CSRF_TRUSTED_ORIGINS")
    if not CORS_ALLOWED_ORIGINS:
        missing_production_settings.append("CORS_ALLOWED_ORIGINS")
    if missing_production_settings:
        raise ImproperlyConfigured(
            "Set the following production settings: "
            + ", ".join(missing_production_settings)
        )

CSRF_FAILURE_VIEW = "config.views.csrf_failure"
COLLEGE_EMAIL_DOMAIN = os.environ.get("COLLEGE_EMAIL_DOMAIN", "gvpcew.ac.in").strip().lower()

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DEBUG and not DATABASE_URL and not os.environ.get("POSTGRES_DB", "").strip():
    raise ImproperlyConfigured(
        "Set DATABASE_URL to a persistent PostgreSQL database in production."
    )

try:
    DATABASE_CONN_MAX_AGE = int(os.environ.get("DB_CONN_MAX_AGE", "0"))
except ValueError as exc:
    raise ImproperlyConfigured("DB_CONN_MAX_AGE must be an integer.") from exc

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts.apps.AccountsConfig",
    "apps.profiles.apps.ProfilesConfig",
    "apps.academics.apps.AcademicsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.questions.apps.QuestionsConfig",
    "apps.social.apps.SocialConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if DATABASE_URL:
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        raise ImproperlyConfigured("DATABASE_URL must use a PostgreSQL URL.")
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=DATABASE_CONN_MAX_AGE,
            ssl_require=True,
        )
    }
elif os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", ""),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", ""),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "OPTIONS": {"sslmode": os.environ.get("POSTGRES_SSLMODE", "require")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": REPOSITORY_ROOT / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = int(
    os.environ.get("SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
CROSS_SITE_SESSION_COOKIES = (
    os.environ.get("CROSS_SITE_SESSION_COOKIES", "True" if not DEBUG else "False")
    .strip()
    .lower()
    in {"1", "true", "yes"}
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG or CROSS_SITE_SESSION_COOKIES
SESSION_COOKIE_SAMESITE = "None" if CROSS_SITE_SESSION_COOKIES else "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG or CROSS_SITE_SESSION_COOKIES
CSRF_COOKIE_SAMESITE = "None" if CROSS_SITE_SESSION_COOKIES else "Lax"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_RATES": {
        "auth_register": "10/hour",
        "auth_login": "10/minute",
    },
}

REPUTATION_POINTS = {
    "question_upvote": 5,
    "question_downvote": -2,
    "answer_upvote": 10,
    "answer_downvote": -2,
    "answer_accepted": 15,
}
