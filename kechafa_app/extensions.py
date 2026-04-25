"""Lightweight extension registry.

The current platform still runs on SQLite helpers, but this module creates a
single place for future integrations such as Redis, JWT, Celery, and Migrate.
"""

from __future__ import annotations

from flask import Flask
from flask_mail import Mail
from authlib.integrations.flask_client import OAuth

mail = Mail()
oauth = OAuth()


class ExtensionRegistry:
    def __init__(self) -> None:
        self.cache = None
        self.rate_limiter = None
        self.jwt = None
        self.celery = None


registry = ExtensionRegistry()


def init_extensions(app: Flask) -> None:
    app.extensions["kechafa_registry"] = registry
    mail.init_app(app)
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )
