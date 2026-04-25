"""Run this script ONCE to authorize Gmail API access.

Usage:
    venv/Scripts/python gmail_auth.py

A browser window will open — sign in with the Gmail account
that will SEND emails. After approval, gmail_token.json is saved.
You never need to run this again (token auto-refreshes).
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS_PATH = "gmail_credentials.json"
TOKEN_PATH = "gmail_token.json"

if not os.path.exists(CREDENTIALS_PATH):
    print(f"ERROR: '{CREDENTIALS_PATH}' not found.")
    print("Download it from Google Cloud Console → APIs & Services → Credentials → your OAuth 2.0 Client ID → Download JSON")
    raise SystemExit(1)

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_PATH, "w") as f:
    f.write(creds.to_json())

print(f"\nDone! Token saved to '{TOKEN_PATH}'")
print("Your Flask app will now use Gmail API to send emails.")
