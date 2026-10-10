"""One-time setup: run this locally to grant this app access to your own
Google Calendar and save a refresh token to credentials/token.json.

Prerequisites (do this in Google Cloud Console yourself):
  1. Create a project, enable the "Google Calendar API".
  2. Create an OAuth client ID of type "Desktop app".
  3. Download its JSON and save it as credentials/credentials.json.

Then run:
    python scripts/google_oauth_setup.py

A browser window opens asking you to log in and approve access to your
own Google account -- this is a one-time local consent, not something this
script or any server does on your behalf.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow

from app.calendar_service import SCOPES
from app.config import settings


def main():
    credentials_path = Path(settings.google_credentials_file)
    if not credentials_path.exists():
        raise SystemExit(
            f"{credentials_path} not found. Download an OAuth client (Desktop app type) "
            "from Google Cloud Console and save it there first."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path(settings.google_token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    print(f"Saved refresh token to {token_path}")


if __name__ == "__main__":
    main()
