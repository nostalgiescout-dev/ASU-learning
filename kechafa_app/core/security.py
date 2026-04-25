"""Shared access-control helpers."""

from __future__ import annotations

from functools import wraps

from flask import flash, redirect, request, session, url_for

from i18n import t
from kechafa_app.repositories.user_repository import UserRepository


user_repo = UserRepository()
ADMIN_LIKE_USERNAMES = {"lead_instructor"}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            lang = session.get("lang", "en")
            flash(t("Please sign in to continue.", lang=lang), "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)

    return decorated


def require_roles(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login"))
            user = user_repo.get_by_id(session["user_id"])
            if not user or user.get("role") not in roles:
                flash("Insufficient permissions.", "danger")
                return redirect(url_for("dashboard.feed"))
            return f(*args, **kwargs)

        return decorated

    return decorator


def is_admin_like_user(user: dict | None) -> bool:
    return bool(user and (user.get("role") == "admin" or user.get("username") in ADMIN_LIKE_USERNAMES))


def can_publish_feed_posts(user: dict | None) -> bool:
    return bool(user and (user.get("role") in {"admin", "instructor"} or is_admin_like_user(user)))


def admin_like_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        user = user_repo.get_by_id(session["user_id"])
        if not is_admin_like_user(user):
            flash("Insufficient permissions.", "danger")
            return redirect(url_for("dashboard.feed"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    return require_roles("admin")(f)


def instructor_required(f):
    return require_roles("admin", "instructor")(f)
