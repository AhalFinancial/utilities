"""Delete all blocker events created by calendarsync from all calendars."""

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from sync import load_config, get_credentials, build_service, MANAGED_BY


def main():
    config = load_config()
    calendars = config["calendars"]
    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=1)).isoformat()
    time_max = (now + timedelta(days=30)).isoformat()

    for cal in calendars:
        creds = get_credentials(cal)
        service = build_service(creds)
        cal_id = cal["id"]
        label = cal["label"]

        # Fetch all managed blocker events
        blockers = []
        page_token = None
        while True:
            resp = service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                privateExtendedProperty=f"managedBy={MANAGED_BY}",
                pageToken=page_token,
                maxResults=250,
            ).execute()
            for event in resp.get("items", []):
                if event.get("status") != "cancelled":
                    blockers.append(event)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        print(f"{label}: found {len(blockers)} blocker events to delete")
        deleted = 0
        for event in blockers:
            for attempt in range(5):
                try:
                    service.events().delete(calendarId=cal_id, eventId=event["id"]).execute()
                    deleted += 1
                    if deleted % 20 == 0:
                        time.sleep(1)
                    break
                except Exception as e:
                    if "rateLimitExceeded" in str(e) and attempt < 4:
                        print(f"  Rate limited, waiting {2 ** attempt}s...")
                        time.sleep(2 ** attempt)
                    else:
                        print(f"  Failed to delete {event['id']}: {e}")
                        break
        print(f"{label}: deleted {deleted} events")


if __name__ == "__main__":
    main()
