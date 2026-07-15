"""
Fortunex Backend — Django Settings
Phase 1: Auth, Users, KYC
"""
from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY — override SECRET_KEY in .env for production
SECRET_KEY = config("SECRET_KEY", default="fortunex-dev-secret-key-change-in-production")
DEBUG      = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")

# ─── Apps ──────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    # Fortunex apps
    "users",
    "trading",
    "bots",
    "market",
    "cashier",
    "affiliate",
    "notifications"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",          # must be before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "fortunex_backend.urls"

TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates",
              "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": [
                  "django.template.context_processors.debug",
                  "django.template.context_processors.request",
                  "django.contrib.auth.context_processors.auth",
                  "django.contrib.messages.context_processors.messages",
              ]}}]

WSGI_APPLICATION = "fortunex_backend.wsgi.application"
ASGI_APPLICATION = "fortunex_backend.asgi.application"

# ─── Channels (WebSocket support for live ticks + position updates) ─────────
REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

import dj_database_url
from decouple import config

DATABASE_URL = config("DATABASE_URL", default=None)

if DATABASE_URL:
    # Railway / Production
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # Local Development
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
# ─── Custom User Model ───────────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

# ─── Password Validation ─────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Django REST Framework ───────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ─── JWT Settings ────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=15),   # short-lived access token
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),        # longer-lived refresh token
    "ROTATE_REFRESH_TOKENS":  True,                     # issue new refresh on every use
    "BLACKLIST_AFTER_ROTATION": True,                   # blacklist old refresh tokens
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ─── CORS (allow frontend dev server) ────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173"
).split(",")
CORS_ALLOW_CREDENTIALS = True

# ─── CSRF (allow frontend dev server) ────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173"
).split(",")


# During local development allow all origins when DEBUG is True to simplify frontend testing
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# ─── Static / Media ──────────────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # Was "whitenoise.storage.CompressedManifestStaticFilesStorage" --
        # swapped for our lenient subclass, see whitenoise_storage.py
        # for exactly why this is needed.
        "BACKEND": "fortunex_backend.whitenoise_storage.LenientManifestStaticFilesStorage",
    },
}

MEDIA_URL   = "/media/"
MEDIA_ROOT  = BASE_DIR / "media"


# ─── M-Pesa Daraja (STK Push) ────────────────────────────────────────────────
MPESA_ENV = config("MPESA_ENV", default="sandbox")  # "sandbox" or "production"
MPESA_BASE_URL = (
    "https://sandbox.safaricom.co.ke" if MPESA_ENV == "sandbox"
    else "https://api.safaricom.co.ke"
)
MPESA_CONSUMER_KEY    = config("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = config("MPESA_SHORTCODE", default="174379")  # Safaricom's shared sandbox test paybill
MPESA_PASSKEY   = config("MPESA_PASSKEY", default="")          # from your Daraja app's sandbox page

# Safaricom's servers call this URL directly -- it MUST be public HTTPS.
# In dev, run `ngrok http 8000` and put the forwarded URL here.
MPESA_CALLBACK_URL = config(
    "MPESA_CALLBACK_URL",
    default="https://CHANGE-ME.ngrok-free.app/api/v1/cashier/mpesa/callback/",
)

# Wallets always stay in USD. This rate only exists at the boundary where
# we build (or interpret) a KES amount for Daraja. Kept in .env, not
# hardcoded, so you can update it without touching code.
USD_TO_KES_RATE = config("USD_TO_KES_RATE", default="129.33", cast=float)

# ─── BluePay (separate M-Pesa STK Push rail, alongside Daraja above) ───────
# BluePay has a single base URL (no sandbox/live split like IntaSend) --
# see bluepay_service.py.
BLUEPAY_CHANNEL_ID = config("BLUEPAY_CHANNEL_ID", default="")
BLUEPAY_API_SECRET = config("BLUEPAY_API_SECRET", default="")

LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Nairobi"
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ─── Jazzmin (admin panel theming) ───────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title": "FortuneX Admin",
    "site_header": "FortuneX",
    "site_brand": "FortuneX",
    "site_logo": None,   # no logo file yet -- once you have one, put it under a static folder
                          # (e.g. static/images/logo.png) and set this to "images/logo.png"
    "login_logo": None,
    "site_icon": None,
    "welcome_sign": "Welcome to FortuneX Admin",
    "copyright": "FortuneX",

    # Models searchable from the top admin search bar, these three cover
    # the most common "find this user / find this transaction" lookups.
    "search_model": ["users.User", "cashier.Deposit", "cashier.Withdrawal"],
    "user_avatar": None,

    "topmenu_links": [
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "users.User"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    # Controls the order apps appear in the sidebar, top to bottom.
    # Auth (Django's built in Users/Groups) pushed to the bottom since
    # your own users.User model is what you actually manage day to day.
    "order_with_respect_to": [
        "users", "cashier", "trading", "bots", "affiliate", "notifications", "market", "auth",
    ],

    # Per model sidebar icons (FontAwesome 5 free, bundled with Jazzmin).
    # Only apps/models I've actually seen the real names of in your code
    # are listed here, see the chat note about "market" specifically.
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-users",

        "users.User": "fas fa-user",
        "users.Wallet": "fas fa-wallet",
        "users.KYCSubmission": "fas fa-id-card",

        "cashier.Deposit": "fas fa-arrow-down",
        "cashier.Withdrawal": "fas fa-arrow-up",

        "trading.MarketInstrument": "fas fa-chart-bar",
        "trading.Tick": "fas fa-wave-square",
        "trading.TradePosition": "fas fa-exchange-alt",
        "trading.BotRun": "fas fa-robot",

        "bots.AutomationProduct": "fas fa-microchip",

        "affiliate.ReferralLink": "fas fa-link",
        "affiliate.ReferralCommission": "fas fa-hand-holding-usd",

        "notifications.Notification": "fas fa-bell",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": False,
    "custom_css": None,
    "custom_js": None,
    "show_ui_builder": False,  # fixed theme via code only, per your answer, no live customizer
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-info",  # closest built in preset to your #00c2b2 teal, see chat note for an exact hex match option
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "theme": "darkly",         # dark theme, closest built in match to your app's own look
    "dark_mode_theme": "darkly",
    "default_theme_mode": "auto",
    "button_classes": {
        "primary": "btn-outline-info",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-outline-success",
    },
    "actions_sticky_top": True,
}