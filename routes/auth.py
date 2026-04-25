"""routes/auth.py - Authentication blueprint."""

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from i18n import t
from kechafa_app.core.security import admin_like_required, admin_required, instructor_required, login_required
from kechafa_app.extensions import oauth
from kechafa_app.services.auth_service import AuthService
from kechafa_app.services.email_service import confirm_verify_token, send_verification_email
from kechafa_app.repositories.user_repository import UserRepository

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()
user_repo = UserRepository()
__all__ = ["auth_bp", "login_required", "admin_required", "admin_like_required", "instructor_required"]


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.feed"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        scout_unit = request.form.get("scout_unit", "").strip()
        lang = request.form.get("lang", "en")

        result = auth_service.register_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            scout_unit=scout_unit,
            lang=lang,
        )

        if not result.ok:
            lang = session.get("lang", "en")
            for error in result.errors:
                flash(t(error, lang=lang), "danger")
            return render_template("auth/register.html", form_data=request.form)

        # Don't log in yet — user must verify email first
        session["lang"] = lang
        return redirect(url_for("auth.email_sent", email=email))

    return render_template("auth/register.html", form_data={})


@auth_bp.route("/email-sent")
def email_sent():
    email = request.args.get("email", "")
    return render_template("auth/email_sent.html", email=email)


@auth_bp.route("/verify/<token>")
def verify_email(token):
    email = confirm_verify_token(token)
    lang = session.get("lang", "en")

    if not email:
        flash(t("Verification link is invalid or has expired. Please request a new one.", lang=lang), "danger")
        return redirect(url_for("auth.login"))

    user = user_repo.get_by_email(email)
    if not user:
        flash(t("Account not found.", lang=lang), "danger")
        return redirect(url_for("auth.login"))

    if user.get("is_verified"):
        flash(t("Your email is already verified. Please sign in.", lang=lang), "info")
        return redirect(url_for("auth.login"))

    user_repo.verify_email(email)
    flash(t("Email verified successfully! You can now sign in.", lang=lang), "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    lang = session.get("lang", "en")

    user = user_repo.get_by_email(email)
    if user and not user.get("is_verified"):
        send_verification_email(email, user["username"])

    # Always show same message to prevent email enumeration
    flash(t("If that email exists and is unverified, a new verification link has been sent.", lang=lang), "info")
    return redirect(url_for("auth.email_sent", email=email))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.feed"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user, reason = auth_service.authenticate(identifier, password)
        if user:
            session["user_id"] = user["id"]
            session["lang"] = user["preferred_lang"]
            lang = session.get("lang", "en")
            flash(t("Welcome back, {name}! 👋", lang=lang, name=user["full_name"] or user["username"]), "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.feed"))

        lang = session.get("lang", "en")
        if reason == "unverified":
            # Find email for resend form
            unverified_user = user_repo.get_by_identifier(identifier)
            unverified_email = unverified_user["email"] if unverified_user else ""
            flash(t("Please verify your email before signing in.", lang=lang), "warning")
            return render_template("auth/login.html", unverified_email=unverified_email)

        flash(t("Invalid credentials. Please try again.", lang=lang), "danger")

    return render_template("auth/login.html", unverified_email="")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("misc.landing"))


@auth_bp.route("/google/login")
def google_login():
    from flask import current_app
    scheme = current_app.config.get("PREFERRED_URL_SCHEME", "https")
    redirect_uri = url_for("auth.google_callback", _external=True, _scheme=scheme)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    from flask import current_app
    lang = session.get("lang", "en")
    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or {}
        email = (info.get("email") or "").lower().strip()
        full_name = info.get("name") or ""
        avatar_url = info.get("picture") or ""

        if not email:
            flash(t("Could not retrieve your Google email. Please try again.", lang=lang), "danger")
            return redirect(url_for("auth.login"))

        user = user_repo.get_by_email(email)

        if user:
            if avatar_url and not (user.get("avatar_url") or "").startswith("http"):
                user_repo.update_avatar(user["id"], avatar_url)
            user = user_repo.get_by_email(email)
        else:
            new_id = user_repo.create_google_user(
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                lang=lang,
            )
            user = user_repo.get_by_id(new_id)

        if not user:
            flash(t("Account error. Please try again.", lang=lang), "danger")
            return redirect(url_for("auth.login"))

        session["user_id"] = user["id"]
        session["lang"] = user.get("preferred_lang") or lang
        flash(t("Welcome, {name}! 👋", lang=lang, name=user.get("full_name") or user.get("username", "")), "success")
        return redirect(url_for("dashboard.feed"))

    except Exception as e:
        current_app.logger.error(f"Google OAuth callback error: {e}")
        flash(t("Google sign-in failed. Please try again.", lang=lang), "danger")
        return redirect(url_for("auth.login"))


@auth_bp.route("/set-lang")
def set_language():
    lang = request.args.get("lang", "en")
    if lang in ["en", "ar", "fr", "es"]:
        session["lang"] = lang
        auth_service.set_language(session.get("user_id"), lang)
    return redirect(request.referrer or url_for("dashboard.feed"))
