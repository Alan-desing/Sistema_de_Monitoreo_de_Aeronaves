import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_number(name, default, cast=float):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return cast(raw.replace(",", "."))
    except ValueError:
        raise ImproperlyConfigured(f"La variable {name}={raw!r} del .env no es un número válido.")


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "rest_framework",
    "channels",
    "accounts",
    "configuration",
    "monitor",
]

MIDDLEWARE = [
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

ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es"
TIME_ZONE = os.environ.get("TZ", "America/Argentina/Buenos_Aires")
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.permissions.SessionAuthentication401",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
    },
}

# Valores iniciales de la configuración editable (configuration.SystemConfig).
# Solo se usan la primera vez, cuando la base todavía no tiene configuración;
# después manda lo que el administrador guarda desde la web.
INITIAL_CONFIG = {
    "zone_name": os.environ.get("ZONE_NAME", "").strip() or "ALERTA CNA 10KM",
    # 35°06'43" S, 58°43'34" W
    "zone_lat": env_number("ZONE_LAT", -35.111944),
    "zone_lon": env_number("ZONE_LON", -58.726111),
    "zone_radius_nm": env_number("ZONE_RADIUS_NM", 5.4),
    "zone_floor_m": env_number("ZONE_FLOOR_M", 0.0),
    "zone_ceiling_m": env_number("ZONE_CEILING_M", 4400.0),
    "poll_interval_s": env_number("POLL_INTERVAL_S", 5, cast=int),
    "query_radius_nm": env_number("QUERY_RADIUS_NM", 50.0),
    "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
    "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
}

# Permite levantar la web sin consultar adsb.fi (p. ej. para depurar).
MONITOR_ENABLED = env_bool("MONITOR_ENABLED", True)

ADSBFI_USER_AGENT = (
    os.environ.get("ADSBFI_USER_AGENT", "").strip()
    or "avion-monitor/0.1 (monitor privado de aeronaves)"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        # httpx registra cada pedido en INFO: con una consulta cada 5 s es ruido.
        "httpx": {"level": "WARNING"},
        "httpcore": {"level": "WARNING"},
    },
}
