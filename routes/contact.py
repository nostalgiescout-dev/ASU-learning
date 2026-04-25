"""routes/contact.py — Contact form with email verification."""

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from kechafa_app.extensions import mail
from kechafa_app.services.gmail_service import is_configured as gmail_configured
from kechafa_app.services.gmail_service import send_email as gmail_send
from models import ContactSubmission, db

ADMIN_CONTACT_EMAIL = "onlyscoutsacademic@gmail.com"

contact_bp = Blueprint("contact", __name__, url_prefix="/contact")

_SALT = "contact-verify-salt"
_TOKEN_MAX_AGE = 3600  # 1 hour


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_token(submission_id: int) -> str:
    return _serializer().dumps(submission_id, salt=_SALT)


def _confirm_token(token: str) -> int | None:
    """Returns submission id if valid, None otherwise."""
    try:
        return _serializer().loads(token, salt=_SALT, max_age=_TOKEN_MAX_AGE)
    except (SignatureExpired, BadSignature):
        return None


def _send_verification_email(name: str, email: str, token: str) -> None:
    verify_url = url_for("contact.verify", token=token, _external=True)

    mail_user = current_app.config.get("MAIL_USERNAME", "")
    if not mail_user:
        current_app.logger.warning(
            f"\n{'='*60}\n"
            f"MAIL NOT CONFIGURED — contact verify link:\n{verify_url}\n"
            f"{'='*60}"
        )
        return

    msg = Message(
        subject="Please verify your contact request — Only Scouts Academy",
        recipients=[email],
    )
    msg.html = render_template(
        "contact/verify_email.html",
        name=name,
        verify_url=verify_url,
    )
    try:
        mail.send(msg)
    except Exception as exc:
        current_app.logger.error(f"Failed to send contact verification email: {exc}")


# ── Routes ────────────────────────────────────────────────────────

@contact_bp.route("/", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        message = request.form.get("message", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if not message or len(message) < 10:
            errors.append("Message must be at least 10 characters.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("contact/form.html", form_data=request.form)

        submission = ContactSubmission(name=name, email=email, message=message)
        try:
            db.session.add(submission)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Sorry, we couldn't save your message. Please try again.", "danger")
            return render_template("contact/form.html", form_data=request.form)

        token = _generate_token(submission.id)
        _send_verification_email(name, email, token)

        return redirect(url_for("contact.submitted", email=email))

    return render_template("contact/form.html", form_data={})


@contact_bp.route("/submitted")
def submitted():
    email = request.args.get("email", "")
    return render_template("contact/submitted.html", email=email)


@contact_bp.route("/quick-send", methods=["POST"])
def quick_send():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    message = request.form.get("message", "").strip()

    errors = []
    if not name:
        errors.append("Name is required.")
    if not email or "@" not in email:
        errors.append("A valid email address is required.")
    if not message or len(message) < 5:
        errors.append("Message must be at least 5 characters.")

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for("misc.landing", _anchor="contact"))

    html_body = (
        f"<h2 style='color:#1e1b4b;'>New Contact Message</h2>"
        f"<p><strong>Name:</strong> {name}</p>"
        f"<p><strong>Email:</strong> <a href='mailto:{email}'>{email}</a></p>"
        f"<hr style='border-color:#e9d5ff;'/>"
        f"<p style='white-space:pre-line;'>{message.replace(chr(10), '<br/>')}</p>"
        f"<hr style='border-color:#e9d5ff;'/>"
        f"<p style='color:#9ca3af;font-size:12px;'>Sent via Only Scouts Academy contact form</p>"
    )

    sent = False
    if gmail_configured():
        sent = gmail_send(
            to=ADMIN_CONTACT_EMAIL,
            subject=f"New Contact: {name} — Only Scouts Academy",
            html_body=html_body,
            reply_to=email,
        )

    if not sent:
        mail_user = current_app.config.get("MAIL_USERNAME", "")
        if mail_user:
            try:
                msg = Message(
                    subject=f"New Contact: {name} — Only Scouts Academy",
                    recipients=[ADMIN_CONTACT_EMAIL],
                    reply_to=email,
                )
                msg.html = html_body
                mail.send(msg)
                sent = True
            except Exception as exc:
                current_app.logger.error(f"Failed to send contact email: {exc}")

    if not sent:
        current_app.logger.warning(
            f"\n{'='*60}\n"
            f"EMAIL NOT CONFIGURED — contact from: {name} <{email}>\n"
            f"Message: {message}\n"
            f"{'='*60}"
        )

    flash("Your message has been sent! We will get back to you soon.", "success")
    return redirect(url_for("misc.landing") + "#contact")


@contact_bp.route("/verify/<token>")
def verify(token):
    submission_id = _confirm_token(token)

    if submission_id is None:
        flash("This verification link is invalid or has expired.", "danger")
        return redirect(url_for("contact.form"))

    submission = db.session.get(ContactSubmission, submission_id)

    if not submission:
        flash("Submission not found.", "danger")
        return redirect(url_for("contact.form"))

    if submission.is_verified or submission.status == "verified":
        flash("This submission has already been verified.", "info")
        return render_template("contact/verified.html", already=True)

    submission.mark_verified()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Sorry, we couldn't verify your submission. Please try again.", "danger")
        return redirect(url_for("contact.form"))

    return render_template("contact/verified.html", already=False, name=submission.name)
