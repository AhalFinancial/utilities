"""One-off cleanup for calendarsync (whole year 2026).

Two operations:
  1. PERSONAL calendar: delete ALL managed blockers. Personal is never its
     own source, so every managed blocker on it is a work->personal sync,
     which the user does not want. (Personal events still sync OUT to work.)
  2. WORK calendars (AHAL, Rutopia, Reurbano): dedupe managed blockers keyed
     by (calendarSyncSource, sourceEventId). Keep the OLDEST copy, delete the
     rest. Removes the runaway duplicates while preserving one blocker per
     real source event (including personal->work).

Personal uses the service account (sa-personal.json) because the OAuth token
is currently invalid. Work calendars use their existing OAuth creds.

Dry-run by default. Pass --yes to actually delete.
"""

import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from sync import load_config, get_credentials, build_service, MANAGED_BY

SCOPES = ["https://www.googleapis.com/auth/calendar"]
YEAR_MIN = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
YEAR_MAX = datetime(2027, 1, 1, tzinfo=timezone.utc).isoformat()

DO_IT = "--yes" in sys.argv


def personal_service():
    cred = SCRIPT_DIR / "credentials" / "sa-personal.json"
    creds = service_account.Credentials.from_service_account_file(str(cred), scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


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


def batch_delete(service, cal_id, ids, label):
    """Delete event ids in batches of 50 with backoff. Returns count deleted.

    404/410 (already gone) count as success. Other per-item failures are
    logged and left for a re-run to mop up (idempotent). Transient batch-level
    errors are retried with exponential backoff.
    """
    if not DO_IT:
        return 0
    stats = {"deleted": 0, "failed": 0}

    def cb(request_id, response, exception):
        if exception is None:
            stats["deleted"] += 1
        else:
            status = getattr(getattr(exception, "resp", None), "status", None)
            if status in (404, 410):  # already gone = success
                stats["deleted"] += 1
            else:
                stats["failed"] += 1

    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        batch = service.new_batch_http_request(callback=cb)
        for j, eid in enumerate(chunk):
            batch.add(service.events().delete(calendarId=cal_id, eventId=eid),
                      request_id=str(i + j))
        for attempt in range(6):
            try:
                batch.execute()
                break
            except HttpError as e:
                if e.resp is not None and e.resp.status in (403, 429, 500, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                else:
                    raise
        time.sleep(0.4)  # gentle pacing between batches
        if (i // 50) % 10 == 0:
            print(f"    {label}: {stats['deleted']} deleted, {stats['failed']} failed...", flush=True)

    if stats["failed"]:
        print(f"    {label}: {stats['failed']} failed (re-run to mop up)")
    return stats["deleted"]


def main():
    config = load_config()
    calendars = config["calendars"]
    id_to_label = {c["id"]: c["label"] for c in calendars}

    print(f"MODE: {'EXECUTE (--yes)' if DO_IT else 'DRY-RUN (no deletions)'}")
    print(f"Window: {YEAR_MIN[:10]} .. {YEAR_MAX[:10]}\n")

    grand = 0

    for cal in calendars:
        cal_id = cal["id"]
        label = cal["label"]
        is_personal = cal.get("personal", False)

        service = personal_service() if is_personal else build_service(get_credentials(cal))
        blockers = fetch_managed(service, cal_id)

        if is_personal:
            # Delete ALL managed blockers (all are work->personal).
            ids = [b["id"] for b in blockers]
            print(f"=== {label} [PERSONAL] ===")
            print(f"  Managed blockers found: {len(blockers)}")
            print(f"  To delete (ALL work->personal): {len(ids)}")
            grand += len(ids)
            if DO_IT and ids:
                n = batch_delete(service, cal_id, ids, label)
                print(f"  Deleted: {n}")
        else:
            # Dedupe by (source, sourceEventId): keep oldest, delete rest.
            groups = defaultdict(list)
            for b in blockers:
                props = (b.get("extendedProperties") or {}).get("private") or {}
                key = (props.get("calendarSyncSource"), props.get("sourceEventId"))
                groups[key].append(b)
            to_delete = []
            for key, grp in groups.items():
                if len(grp) <= 1:
                    continue
                grp_sorted = sorted(grp, key=lambda e: e.get("created", ""))
                to_delete.extend(e["id"] for e in grp_sorted[1:])
            print(f"=== {label} ===")
            print(f"  Managed blockers: {len(blockers)}  unique keys: {len(groups)}")
            print(f"  Duplicate copies to delete: {len(to_delete)}")
            grand += len(to_delete)
            if DO_IT and to_delete:
                n = batch_delete(service, cal_id, to_delete, label)
                print(f"  Deleted: {n}")
        print()

    print(f"GRAND TOTAL to delete: {grand}")
    if not DO_IT:
        print("(dry-run — rerun with --yes to execute)")


if __name__ == "__main__":
    main()
