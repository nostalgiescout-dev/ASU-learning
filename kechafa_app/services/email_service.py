from __future__ import annotations

from flask import current_app, render_template, url_for
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from kechafa_app.extensions import mail
from kechafa_app.services.gmail_service import is_configured as gmail_configured
from kechafa_app.services.gmail_service import send_email as gmail_send

TOKEN_SALT = "email-verify-salt"
TOKEN_MAX_AGE = 3600  # 1 hour


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_verify_token(email: str) -> str:
    return _serializer().dumps(email, salt=TOKEN_SALT)


def confirm_verify_token(token: str) -> str | None:
    """Returns email if token is valid, None otherwise."""
    try:
        email = _serializer().loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        return email
    except (SignatureExpired, BadSignature):
        return None


def send_verification_email(email: str, username: str) -> bool:
    """Send verification email. Returns True on success."""
    mail_user = current_app.config.get("MAIL_USERNAME", "")
    if not mail_user:
        # No credentials configured — print token URL to console for dev testing
        token = generate_verify_token(email)
        verify_url = url_for("auth.verify_email", token=token, _external=True)
        current_app.logger.warning(
            f"\n{'='*60}\n"
            f"EMAIL NOT CONFIGURED — dev verification link:\n{verify_url}\n"
            f"{'='*60}"
        )
        return False

    try:
        token = generate_verify_token(email)
        verify_url = url_for("auth.verify_email", token=token, _external=True)
        html_body = render_template(
            "auth/verify_email_body.html",
            username=username,
            verify_url=verify_url,
        )

        if gmail_configured():
            return gmail_send(
                to=email,
                subject="Verify your Only Scouts Academy account",
                html_body=html_body,
            )

        msg = Message(
            subject="Verify your Only Scouts Academy account",
            recipients=[email],
        )
        msg.html = html_body
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send verification email to {email}: {e}")
        return False
