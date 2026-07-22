"""Dedupe calendarsync blocker events over an arbitrary date range.

Generalises dedupe.py (which was hardcoded to May+June 2026) so it can clean
the *future* weeks where the sync super-duplicated blockers.

For each (summary, start, end) group with >1 event on a calendar:
- Keep the OLDEST one (lowest 'created' timestamp)
- Delete the rest, but ONLY if every event in the group is a calendarsync
  blocker (managedBy=calendarsync). Mixed/non-blocker groups are skipped.

Dry-run by default. Pass --yes to actually delete.

Usage:
  python dedupe_range.py                       # scan now .. now+42d (dry run)
  python dedupe_range.py --from 2026-07-22 --to 2026-09-01
  python dedupe_range.py --yes                 # actually delete
"""

import argparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from sync import load_config, get_credentials, build_service, MANAGED_BY


def is_blocker(event):
    props = (event.get("extendedProperties") or {}).get("private") or {}
    return props.get("managedBy") == MANAGED_BY


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="date_from", default=None,
                   help="Start date YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--to", dest="date_to", default=None,
                   help="End date YYYY-MM-DD exclusive (default: from + 42 days)")
    p.add_argument("--yes", action="store_true",
                   help="Actually delete. Without it, dry-run scan only.")
    return p.parse_args()


def main():
    args = parse_args()
    now = datetime.now(timezone.utc)

    if args.date_from:
        start = datetime.fromisoformat(args.date_from).replace(tzinfo=timezone.utc)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if args.date_to:
        end = datetime.fromisoformat(args.date_to).replace(tzinfo=timezone.utc)
    else:
        end = start + timedelta(days=42)

    time_min = start.isoformat()
    time_max = end.isoformat()
    dry = not args.yes

    print(f"{'DRY RUN — ' if dry else ''}Dedupe window: {time_min[:10]} .. {time_max[:10]}")
    print()

    config = load_config()
    calendars = config["calendars"]

    grand_deleted = grand_would = grand_skipped = 0

    for cal in calendars:
        try:
            creds = get_credentials(cal)
            service = build_service(creds)
        except Exception as e:
            print(f"{cal['label']}: AUTH FAILED - {e} (skipping)")
            continue
        cal_id = cal["id"]
        label = cal["label"]

        events = []
        page_token = None
        while True:
            resp = service.events().list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                pageToken=page_token,
                maxResults=250,
            ).execute()
            events.extend(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        groups = defaultdict(list)
        for e in events:
            if e.get("status") == "cancelled":
                continue
            summary = e.get("summary", "(no title)")
            s = (e.get("start", {}).get("dateTime")
                 or e.get("start", {}).get("date") or "")
            en = (e.get("end", {}).get("dateTime")
                  or e.get("end", {}).get("date") or "")
            groups[(summary, s, en)].append(e)

        deleted = would = skipped = 0
        sample = []
        for (summary, s, _en), grp in groups.items():
            if len(grp) <= 1:
                continue
            if not all(is_blocker(e) for e in grp):
                skipped += 1
                continue

            grp_sorted = sorted(grp, key=lambda e: e.get("created", ""))
            to_delete = grp_sorted[1:]
            would += len(to_delete)
            if len(sample) < 10:
                sample.append(f"    {len(grp):3d}x  {s[:16]}  {summary[:50]}")

            if dry:
                continue

            for ev in to_delete:
                for attempt in range(5):
                    try:
                        service.events().delete(
                            calendarId=cal_id, eventId=ev["id"]
                        ).execute()
                        deleted += 1
                        if deleted % 25 == 0:
                            time.sleep(1)
                        break
                    except Exception as ex:
                        msg = str(ex)
                        if ("rateLimitExceeded" in msg
                                or "userRateLimitExceeded" in msg) and attempt < 4:
                            time.sleep(2 ** attempt)
                        elif "410" in msg or "Resource has been deleted" in msg:
                            deleted += 1
                            break
                        else:
                            print(f"  [{label}] failed {ev['id']}: {msg[:120]}")
                            break

        if dry:
            print(f"{label}: {len(events)} events, would delete {would} extra copies"
                  + (f", {skipped} groups skipped (non-blocker)" if skipped else ""))
            for line in sample:
                print(line)
        else:
            print(f"{label}: deleted {deleted} extras"
                  + (f", skipped {skipped} groups (non-blocker)" if skipped else ""))

        grand_deleted += deleted
        grand_would += would
        grand_skipped += skipped

    print()
    if dry:
        print(f"TOTAL would delete: {grand_would} extra copies across all calendars")
        print("Re-run with --yes to delete.")
    else:
        print(f"TOTAL deleted: {grand_deleted}")
    if grand_skipped:
        print(f"TOTAL groups skipped (mixed/non-blocker): {grand_skipped}")


if __name__ == "__main__":
    main()
