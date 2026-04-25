"""One-time OAuth setup for calendars that need OAuth auth.

Usage:
    python calendarsync/setup_oauth.py reurbano
    python calendarsync/setup_oauth.py rutopia

This opens a browser for Google sign-in, then saves the token
to credentials/oauth-{name}.json for use by sync.py.
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SCRIPT_DIR = Path(__file__).parent
CREDS_DIR = SCRIPT_DIR / "credentials"

# Maps calendar name to its OAuth client secret file
CLIENT_FILES = {
    "reurbano": "oauth-reurbano-client.json",
    "rutopia": "oauth-rutopia-client.json",
    "ahal": "oauth-ahal-client.json",
    "personal": "oauth-personal-client.json",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CLIENT_FILES:
        print(f"Usage: python setup_oauth.py <{'|'.join(CLIENT_FILES.keys())}>")
        sys.exit(1)

    name = sys.argv[1]
    client_file = CREDS_DIR / CLIENT_FILES[name]
    token_output = CREDS_DIR / f"oauth-{name}.json"

    if not client_file.exists():
        print(f"Client secret file not found: {client_file}")
        sys.exit(1)

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

    env_var = f"GOOGLE_OAUTH_{name.upper()}"
    print(f"Token saved to {token_output}")
    print(f"For GitHub Actions, set {env_var} secret to the contents of this file.")


if __name__ == "__main__":
    main()
