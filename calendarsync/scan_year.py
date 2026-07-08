"""Read-only scan of calendarsync blockers for the whole year.

For each calendar, reports:
- total managed blockers
- breakdown by source calendar
- exact duplicates keyed by (calendarSyncSource, sourceEventId)

Also flags, for the Personal calendar, how many blockers come from work
calendars (which is all of them, since Personal is never its own source).

Read-only. Deletes nothing.
"""

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from sync import load_config, get_credentials, build_service, MANAGED_BY

YEAR_MIN = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
YEAR_MAX = datetime(2027, 1, 1, tzinfo=timezone.utc).isoformat()


def fetch_managed(service, cal_id):
    blockers = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=cal_id,
            timeMin=YEAR_MIN,
            timeMax=YEAR_MAX,
            singleEvents=True,
            privateExtendedProperty=f"managedBy={MANAGED_BY}",
            pageToken=page_token,
            maxResults=250,
        ).execute()
        for e in resp.get("items", []):
            if e.get("status") != "cancelled":
                blockers.append(e)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return blockers


def main():
    config = load_config()
    calendars = config["calendars"]
    id_to_label = {c["id"]: c["label"] for c in calendars}

    for cal in calendars:
        creds = get_credentials(cal)
        service = build_service(creds)
        cal_id = cal["id"]
        label = cal["label"]
        is_personal = cal.get("personal", False)

        blockers = fetch_managed(service, cal_id)

        by_source = defaultdict(int)
        dup_key = defaultdict(list)
        for b in blockers:
            props = (b.get("extendedProperties") or {}).get("private") or {}
            src = props.get("calendarSyncSource", "(unknown)")
            sid = props.get("sourceEventId", "(none)")
            by_source[src] += 1
            dup_key[(src, sid)].append(b)

        extra_dups = sum(len(v) - 1 for v in dup_key.values() if len(v) > 1)

        print(f"\n=== {label} ({cal_id}){' [PERSONAL]' if is_personal else ''} ===")
        print(f"  Total managed blockers: {len(blockers)}")
        print(f"  Unique (source,event) keys: {len(dup_key)}")
        print(f"  Extra duplicate copies: {extra_dups}")
        print("  By source calendar:")
        for src, n in sorted(by_source.items(), key=lambda kv: -kv[1]):
            print(f"    {id_to_label.get(src, src):12s} -> {n}")

        if is_personal:
            work = sum(n for s, n in by_source.items() if s != cal_id)
            print(f"  >> Work-sourced blockers on PERSONAL (to delete): {work}")


if __name__ == "__main__":
    main()
