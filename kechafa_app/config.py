"""Centralized configuration for Academic Kechafa."""

from __future__ import annotations

import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "kechafa-dev-secret-2024")
    DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "en")
    DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///kechafa.db")
    KECHAFA_DB = os.environ.get("KECHAFA_DB", "kechafa.db")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_FALLBACK_API_KEY = os.environ.get("OPENROUTER_FALLBACK_API_KEY", "")
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
    OPENROUTER_MAX_TOKENS = int(os.environ.get("OPENROUTER_MAX_TOKENS", "512"))
    OPENROUTER_APP_URL = os.environ.get("OPENROUTER_APP_URL", "")
    OPENROUTER_APP_TITLE = os.environ.get("OPENROUTER_APP_TITLE", "Academic Kechafa")
    ENABLE_REAL_AI = os.environ.get("ENABLE_REAL_AI", "false").lower() == "true"
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "250")) * 1024 * 1024
    JSON_SORT_KEYS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "http")
    FORCE_HTTPS = os.environ.get("FORCE_HTTPS", "false").lower() == "true"
    TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    # Email (Flask-Mail)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Only Scouts Academy <noreply@onlyscouts.com>")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    KECHAFA_DB = os.environ.get("TEST_DATABASE_URL", ":memory:")
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None):
    if not name:
        name = os.environ.get("FLASK_ENV", "development")
    return CONFIG_MAP.get(name, DevelopmentConfig)
