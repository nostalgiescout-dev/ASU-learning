"""Gmail API email service — replaces Flask-Mail SMTP."""
from __future__ import annotations

import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

_BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(_BASE, "gmail_token.json")
CREDENTIALS_PATH = os.path.join(_BASE, "gmail_credentials.json")


def _get_service():
    """Return an authenticated Gmail API service, or None if not configured."""
    if not os.path.exists(TOKEN_PATH):
        return None

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_PATH, "w") as f:
                    f.write(creds.to_json())
            except Exception:
                return None
        else:
            return None

    try:
        return build("gmail", "v1", credentials=creds)
    except Exception:
        return None


def send_email(to: str, subject: str, html_body: str, reply_to: str | None = None) -> bool:
    """Send an email via Gmail API. Returns True on success."""
    service = _get_service()
    if not service:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = to
    msg["From"] = "Only Scouts Academy <onlyscoutsacademic@gmail.com>"
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except HttpError as e:
        print(f"[Gmail API] Send failed: {e}")
        return False


def is_configured() -> bool:
    return os.path.exists(TOKEN_PATH)
