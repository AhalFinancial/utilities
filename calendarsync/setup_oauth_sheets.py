"""One-time OAuth setup with Calendar + Sheets scopes.

Usage:
    python calendarsync/setup_oauth_sheets.py rutopia
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
SCRIPT_DIR = Path(__file__).parent
CREDS_DIR = SCRIPT_DIR / "credentials"

CLIENT_FILES = {
    "reurbano": "oauth-reurbano-client.json",
    "rutopia": "oauth-rutopia-client.json",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CLIENT_FILES:
        print(f"Usage: python setup_oauth_sheets.py <{'|'.join(CLIENT_FILES.keys())}>")
        sys.exit(1)

    name = sys.argv[1]
    client_file = CREDS_DIR / CLIENT_FILES[name]
    token_output = CREDS_DIR / f"oauth-{name}.json"

    flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes),
    }

    with open(token_output, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Token saved to {token_output}")


if __name__ == "__main__":
    main()
