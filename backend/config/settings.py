"""
Django settings for config project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-unsafe-key-change-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")
if not DEBUG and SECRET_KEY == "dev-only-unsafe-key-change-in-production":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY before running with DJANGO_DEBUG=false.")
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_cors_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# OpenAI-compatible API (set OPENAI_BASE_URL for Azure or other proxies).
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip()

# Demo safety limits. These keep uploaded data and regex work bounded for a
# take-home deployment without adding a background worker or persistent store.
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_UPLOAD_ROWS = int(os.environ.get("MAX_UPLOAD_ROWS", "10000"))
MAX_UPLOAD_COLUMNS = int(os.environ.get("MAX_UPLOAD_COLUMNS", "100"))
MAX_CELL_CHARS = int(os.environ.get("MAX_CELL_CHARS", "2000"))
MAX_REGEX_PATTERN_LENGTH = int(os.environ.get("MAX_REGEX_PATTERN_LENGTH", "500"))
REGEX_TIMEOUT_SECONDS = float(os.environ.get("REGEX_TIMEOUT_SECONDS", "0.05"))
if REGEX_TIMEOUT_SECONDS <= 0:
    raise ImproperlyConfigured("REGEX_TIMEOUT_SECONDS must be greater than zero.")
MAX_REPLACEMENT_CHARS = int(os.environ.get("MAX_REPLACEMENT_CHARS", "10000"))
MAX_SAMPLE_SCAN_ROWS = int(os.environ.get("MAX_SAMPLE_SCAN_ROWS", "250"))
UPLOAD_STORE_TTL_SECONDS = int(os.environ.get("UPLOAD_STORE_TTL_SECONDS", "3600"))
UPLOAD_STORE_MAX_ITEMS = int(os.environ.get("UPLOAD_STORE_MAX_ITEMS", "25"))
EXPORT_STORE_MAX_ITEMS = int(os.environ.get("EXPORT_STORE_MAX_ITEMS", "25"))
