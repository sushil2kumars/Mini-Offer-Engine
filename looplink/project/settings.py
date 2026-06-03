from pathlib import Path

import environ

# ─── Bootstrapping ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
env.read_env(BASE_DIR / ".env")

# ─── ENVIRONMENT FLAGS ─────────────────────────────────────────────────────────
DEBUG = env.bool("DEBUG", default=False)

# ─── CORE SETTINGS ──────────────────────────────────────────────────────────────
SECRET_KEY = env.str("SECRET_KEY", default="you-should-really-change-this")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
TIME_ZONE = env.str("TIME_ZONE", default="UTC")
USE_TZ = True


# ─── APPLICATIONS ──────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
THIRD_PARTY_APPS = [
    "django_components",
    "django_htmx",  # not to be confused with DjangoHtmxActionMixin (our own extension in django_ext)
    "rest_framework",
]
PROJECT_APPS = [
    "looplink.django_ext",
]
UI_APPS = [
    "looplink.ui.base",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + PROJECT_APPS + UI_APPS

# ─── MIDDLEWARE ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "looplink.django_ext.middleware.htmx.HtmxActionMiddleware",
]

# ─── URLS / WSGI ─────────────────────────────────────────────────────────────────
ROOT_URLCONF = "looplink.project.urls"
WSGI_APPLICATION = "looplink.project.wsgi.application"

# ─── TEMPLATES ─────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
            ],
            "debug": DEBUG,
            "libraries": {
                "django_components": "django_components.templatetags.component_tags",
            },
        },
    },
]

# ─── DATABASES ─────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DJANGO_DATABASE_NAME", default="interview"),
        "USER": env("DJANGO_DATABASE_USER", default="postgres"),
        "PASSWORD": env("DJANGO_DATABASE_PASSWORD", default="postgres"),
        "HOST": env("DJANGO_DATABASE_HOST", default="localhost"),
        "PORT": env("DJANGO_DATABASE_PORT", default="5432"),
    }
}

DB_REPLICAS = []

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── CACHES & SESSIONS ──────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
        "OPTIONS": {
            "health_check_interval": 30,
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    },
    "locmem": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "locmem-cache",
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"


# ─── EMAIL ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")
SERVER_EMAIL = env("SERVER_EMAIL", default="errors@example.com")

# ─── STATICFILES ──────────────────────────────────────────────────────────────
BASE_ADDRESS = env("BASE_ADDRESS", default="localhost:8000")

# This is a custom setting to be used with our webpack build using the js_entry templatetags.
BUNDLED_ASSETS_ROOT = BASE_DIR / "bundled_assets"
WEBPACK_BUILD_DIR = BASE_DIR / "webpack/_build"
WEBPACK_BUILT_ASSETS_FOLDER = "webpack"

STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)
STATICFILES_DIRS = [
    BUNDLED_ASSETS_ROOT,
]

STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
STATIC_URL = "/static/"
MEDIA_URL = "/media/"


# ─── LOGGING ───────────────────────────────────────────────────────────────────
LOGGING_DEBUG = env.bool("LOGGING_DEBUG", default=False)
LOG_LEVEL = "DEBUG"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s",
        },
        "simple": {
            "format": "%(levelname)s %(asctime)s [%(module)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
        "django.server": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django_components": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}

# ─── DRF ────────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}
