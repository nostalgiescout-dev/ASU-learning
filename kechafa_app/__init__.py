"""Application package for the upgraded Academic Kechafa platform."""

from pathlib import Path
import os

from flask import Flask, g, redirect, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from database import init_db
from i18n import TRANSLATIONS, t as translate
from kechafa_app.api import register_blueprints
from kechafa_app.core.errors import register_error_handlers
from kechafa_app.core.security import is_admin_like_user
from kechafa_app.extensions import init_extensions

SUPPORTED_LANGUAGES = ["en", "ar", "fr", "es"]


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def create_app(config_name: str | None = None, config_overrides: dict | None = None) -> Flask:
    _load_local_env()
    from kechafa_app.config import get_config
    from models import init_models

    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(get_config(config_name))
    if config_overrides:
        app.config.update(config_overrides)

    # Keep the legacy SQLite helpers (KECHAFA_DB) aligned with SQLAlchemy (DATABASE_URL)
    # unless the user explicitly provides a DATABASE_URL (e.g., Postgres in production).
    if not os.environ.get("DATABASE_URL"):
        kechafa_db = app.config.get("KECHAFA_DB") or "kechafa.db"
        app.config["DATABASE_URL"] = f"sqlite:///{kechafa_db}"

    if app.config.get("TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # type: ignore[assignment]

    init_extensions(app)
    init_models(app)

    with app.app_context():
        init_db()

    @app.before_request
    def enforce_https() -> object | None:
        if app.config.get("FORCE_HTTPS") and not request.is_secure:
            return redirect(request.url.replace("http://", "https://", 1), code=301)
        return None

    @app.before_request
    def resolve_locale() -> None:
        lang = request.args.get("lang")
        if lang and lang in SUPPORTED_LANGUAGES:
            session["lang"] = lang
            if session.get("user_id"):
                from database import execute

                execute(
                    "UPDATE users SET preferred_lang=? WHERE id=?",
                    (lang, session["user_id"]),
                )
        g.lang = session.get("lang", app.config["DEFAULT_LANGUAGE"])
        g.is_rtl = g.lang == "ar"

    @app.context_processor
    def inject_globals():
        from database import fetchone

        user = None
        notif_count = 0
        if session.get("user_id"):
            user = fetchone("SELECT * FROM users WHERE id=?", (session["user_id"],))
            row = fetchone(
                "SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND is_read=0",
                (session["user_id"],),
            )
            notif_count = row["c"] if row else 0
        return {
            "current_user": user,
            "has_admin_like_access": is_admin_like_user(user),
            "current_locale": g.lang,
            "is_rtl": g.is_rtl,
            "supported_languages": SUPPORTED_LANGUAGES,
            "ui_translations": TRANSLATIONS,
            "notif_count": notif_count,
            "_": lambda key, **kwargs: translate(key, g.lang, **kwargs),
        }

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com "
                "https://code.iconify.design; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.iconify.design;"
            )
        return response

    from flask_compress import Compress
    Compress(app)

    register_blueprints(app)
    register_error_handlers(app)
    return app
