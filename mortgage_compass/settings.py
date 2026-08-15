import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-secret-key-mortgage-compass-secure-local-2026"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

ROOT_URLCONF = "mortgage_compass.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "mortgage_compass.wsgi.application"

# Persistent database directory support (e.g. for Unraid volume /data or local)
DB_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_PATH,
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
            "timeout": 20,
        },
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "web" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
RATEAPI_KEY = os.environ.get("RATEAPI_KEY", "")
RATEAPI_BUCKET_SIZE = int(os.environ.get("RATEAPI_BUCKET_SIZE", "25000"))
RATEAPI_SAFETY_THRESHOLD = int(os.environ.get("RATEAPI_SAFETY_THRESHOLD", "18"))
RATEAPI_CACHE_TTL_DAYS = int(os.environ.get("RATEAPI_CACHE_TTL_DAYS", "7"))  # Default: 1 week (7 days)

