from functools import wraps

from flask import flash, redirect, session, url_for

from database import fetchone


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login"))

            user = fetchone("SELECT role FROM users WHERE id=?", (user_id,))
            if not user or user["role"] not in roles:
                flash("You do not have permission to access this page.", "danger")
                return redirect(url_for("dashboard.feed"))
            return f(*args, **kwargs)

        return decorated_function

    return decorator
