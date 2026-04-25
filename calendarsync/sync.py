"""Calendar Sync - Create blocker events across Google Calendars."""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]
MANAGED_BY = "calendarsync"
SCRIPT_DIR = Path(__file__).parent
CREDS_DIR = SCRIPT_DIR / "credentials"

# Re-baseline (full list) at most every BASELINE_MAX_AGE so the timeMin/timeMax
# window stays roughly aligned with the configured sync_window_days as time
# advances. Between baselines, syncToken returns only changed events.
BASELINE_MAX_AGE = timedelta(hours=24)
DEFAULT_CACHE_DIR = Path.cwd() / ".sync-cache"

# Per-calendar credential mappings
CRED_MAP = {
    "ahal": {
        "type": "service_account_delegated",
        "env": "GOOGLE_SA_AHAL",
        "file": "sa-ahal.json",
        "subject": "eduardo@ahalfinancial.com",
    },
    "rutopia": {
        "type": "oauth",
        "env": "GOOGLE_OAUTH_RUTOPIA",
        "file": "oauth-rutopia.json",
    },
    "reurbano": {
        "type": "oauth",
        "env": "GOOGLE_OAUTH_REURBANO",
        "file": "oauth-reurbano.json",
    },
    "personal": {
        "type": "service_account",
        "env": "GOOGLE_SA_PERSONAL",
        "file": "sa-personal.json",
    },
}


def load_config():
    with open(SCRIPT_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


def load_sa_credentials(env_var, filename, subject=None):
    """Load service account credentials, optionally with domain-wide delegation."""
    env_json = os.environ.get(env_var)
    if env_json:
        info = json.loads(env_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        path = CREDS_DIR / filename
        if path.exists():
            creds = service_account.Credentials.from_service_account_file(str(path), scopes=SCOPES)
        else:
            raise RuntimeError(f"No credentials found. Set {env_var} env var or place {filename} in credentials/")

    if subject:
        creds = creds.with_subject(subject)
    return creds


def load_oauth_credentials(env_var, filename):
    """Load OAuth credentials from env var or local file."""
    env_json = os.environ.get(env_var)
    if env_json:
        token_data = json.loads(env_json)
    else:
        path = CREDS_DIR / filename
        if path.exists():
            with open(path) as f:
                token_data = json.load(f)
        else:
            raise RuntimeError(
                f"No OAuth credentials found. Run setup_oauth.py first, "
                f"or set {env_var} env var."
            )

    return Credentials(
        token=token_data.get("token"),
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=SCOPES,
    )


def get_credentials(cal_config):
    """Get credentials for a calendar based on its auth config."""
    key = cal_config["label"].lower()
    cred_info = CRED_MAP.get(key)
    if not cred_info:
        raise RuntimeError(f"No credential mapping for calendar '{cal_config['label']}'")

    cred_type = cred_info["type"]
    if cred_type == "service_account":
        return load_sa_credentials(cred_info["env"], cred_info["file"])
    elif cred_type == "service_account_delegated":
        return load_sa_credentials(cred_info["env"], cred_info["file"], subject=cred_info["subject"])
    elif cred_type == "oauth":
        return load_oauth_credentials(cred_info["env"], cred_info["file"])
    else:
        raise RuntimeError(f"Unknown auth type '{cred_type}' for {cal_config['label']}")


def build_service(credentials):
    return build("calendar", "v3", credentials=credentials)


def get_time_window(days):
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days)).isoformat()
    return time_min, time_max


def get_cache_dir():
    return Path(os.environ.get("CALENDARSYNC_CACHE_DIR") or DEFAULT_CACHE_DIR)


def load_token_store():
    path = get_cache_dir() / "sync_tokens.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Warning: could not read token cache ({e}); starting from baseline.")
        return {}


def save_token_store(store):
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "sync_tokens.json"
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(store, f, indent=2, sort_keys=True)
    tmp.replace(path)


def _list_events(service, calendar_id, time_min, time_max, sync_token):
    """Single list pass. With sync_token, pulls deltas; otherwise baseline."""
    events = []
    page_token = None
    next_sync_token = None
    while True:
        kwargs = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "showDeleted": True,
            "maxResults": 250,
        }
        if sync_token:
            kwargs["syncToken"] = sync_token
        else:
            kwargs["timeMin"] = time_min
            kwargs["timeMax"] = time_max
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.events().list(**kwargs).execute()
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            next_sync_token = resp.get("nextSyncToken")
            break
    return events, next_sync_token


def fetch_events_delta(service, calendar_id, time_min, time_max, sync_token):
    """Fetch events incrementally when possible; baseline otherwise.

    Returns (events, new_sync_token, was_baseline). Cancelled events are
    included so callers can react to deletions. On 410 GONE the syncToken is
    expired and we transparently re-baseline.
    """
    was_baseline = sync_token is None
    try:
        events, new_token = _list_events(service, calendar_id, time_min, time_max, sync_token)
    except HttpError as e:
        if sync_token and getattr(e, "resp", None) is not None and e.resp.status == 410:
            print(f"    syncToken expired for {calendar_id}; re-baselining")
            events, new_token = _list_events(service, calendar_id, time_min, time_max, None)
            was_baseline = True
        else:
            raise
    return events, new_token, was_baseline


def fetch_managed_blockers(service, calendar_id, time_min, time_max):
    """Fetch blocker events created by this tool on a target calendar."""
    blockers = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            privateExtendedProperty=f"managedBy={MANAGED_BY}",
            pageToken=page_token,
            maxResults=250,
        ).execute()
        for event in resp.get("items", []):
            if event.get("status") == "cancelled":
                continue
            blockers.append(event)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return blockers


def compute_fingerprint(event):
    """Hash of start/end/attendee count to detect changes."""
    start = event.get("start", {}).get("dateTime", "")
    end = event.get("end", {}).get("dateTime", "")
    attendee_count = len(event.get("attendees", []))
    raw = f"{start}|{end}|{attendee_count}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def make_blocker_summary(cal_config, event):
    """Generate the blocker event summary based on naming rules."""
    label = cal_config["label"]
    is_personal = cal_config.get("personal", False)
    attendees = event.get("attendees", [])
    has_others = len(attendees) > 1

    if is_personal:
        return "Busy - Personal" if has_others else "Focus - Personal"
    else:
        return f"Meeting - {label}" if has_others else f"Focus - {label}"


def build_blocker_body(source_event, source_cal_id, cal_config):
    """Build the event body for a blocker event."""
    fingerprint = compute_fingerprint(source_event)
    summary = make_blocker_summary(cal_config, source_event)

    return {
        "summary": summary,
        "start": source_event["start"],
        "end": source_event["end"],
        "transparency": "opaque",
        "extendedProperties": {
            "private": {
                "managedBy": MANAGED_BY,
                "calendarSyncSource": source_cal_id,
                "sourceEventId": source_event["id"],
                "fingerprint": fingerprint,
            }
        },
    }


def sync_pair(target_service, source_cal, target_cal, source_events, time_min, time_max):
    """Reconcile a precomputed source delta against blockers on the target."""
    source_id = source_cal["id"]
    target_id = target_cal["id"]

    existing_blockers = fetch_managed_blockers(target_service, target_id, time_min, time_max)

    blocker_map = {}
    for b in existing_blockers:
        props = b.get("extendedProperties", {}).get("private", {})
        if props.get("calendarSyncSource") == source_id:
            key = props.get("sourceEventId")
            if key:
                blocker_map[key] = b

    created = updated = deleted = 0

    for event in source_events:
        existing = blocker_map.get(event["id"])

        if event.get("status") == "cancelled":
            if existing is not None:
                target_service.events().delete(
                    calendarId=target_id, eventId=existing["id"]
                ).execute()
                deleted += 1
            continue

        # Skip all-day events (only date, no dateTime)
        if "dateTime" not in event.get("start", {}):
            continue

        # Skip blocker events created by this tool to prevent cascading
        props = event.get("extendedProperties", {}).get("private", {})
        if props.get("managedBy") == MANAGED_BY:
            continue

        fingerprint = compute_fingerprint(event)

        if existing is None:
            body = build_blocker_body(event, source_id, source_cal)
            target_service.events().insert(calendarId=target_id, body=body).execute()
            created += 1
        else:
            existing_fp = existing.get("extendedProperties", {}).get("private", {}).get("fingerprint", "")
            if existing_fp != fingerprint:
                body = build_blocker_body(event, source_id, source_cal)
                target_service.events().update(
                    calendarId=target_id, eventId=existing["id"], body=body
                ).execute()
                updated += 1

    return created, updated, deleted


def main():
    config = load_config()
    calendars = config["calendars"]
    time_min, time_max = get_time_window(config.get("sync_window_days", 14))
    now = datetime.now(timezone.utc)

    print(f"Calendar Sync starting at {now.isoformat()}")
    print(f"Window: {time_min} to {time_max}")
    print(f"Calendars: {[c['label'] for c in calendars]}")
    print()

    services = {}
    for cal in calendars:
        try:
            creds = get_credentials(cal)
            services[cal["id"]] = build_service(creds)
            print(f"  Auth OK: {cal['label']}")
        except Exception as e:
            print(f"  Auth FAILED: {cal['label']} - {e}")
            sys.exit(1)
    print()

    token_store = load_token_store()
    deltas_by_source = {}
    errors = []

    # Phase 1: pull deltas (or baseline) per source calendar
    for source_cal in calendars:
        source_id = source_cal["id"]
        entry = token_store.get(source_id) or {}
        prior_token = entry.get("token")
        baseline_at_iso = entry.get("baseline_at")

        if prior_token and baseline_at_iso:
            try:
                age = now - datetime.fromisoformat(baseline_at_iso)
                if age >= BASELINE_MAX_AGE:
                    prior_token = None  # force re-baseline to refresh window
            except ValueError:
                prior_token = None

        try:
            events, new_token, was_baseline = fetch_events_delta(
                services[source_id], source_id, time_min, time_max, prior_token,
            )
        except HttpError as e:
            print(f"  {source_cal['label']}: list FAILED - {e}")
            errors.append(f"list:{source_cal['label']}")
            continue

        deltas_by_source[source_id] = {
            "events": events,
            "new_token": new_token,
            "was_baseline": was_baseline,
            "prior_baseline_at": baseline_at_iso,
        }
        kind = "baseline" if was_baseline else "delta"
        print(f"  {source_cal['label']}: {len(events)} event(s) in {kind}")
    print()

    # Phase 2: reconcile each non-empty delta against every target
    total_created = total_updated = total_deleted = 0
    failed_sources = set()

    for source_cal in calendars:
        source_id = source_cal["id"]
        delta = deltas_by_source.get(source_id)
        if not delta:
            continue
        events = delta["events"]
        if not events:
            continue

        for target_cal in calendars:
            if target_cal["id"] == source_id:
                continue
            pair_label = f"{source_cal['label']} -> {target_cal['label']}"
            try:
                created, updated, deleted = sync_pair(
                    services[target_cal["id"]],
                    source_cal, target_cal,
                    events, time_min, time_max,
                )
                total_created += created
                total_updated += updated
                total_deleted += deleted
                if created or updated or deleted:
                    print(f"  {pair_label}: +{created} ~{updated} -{deleted}")
                else:
                    print(f"  {pair_label}: no changes")
            except Exception as e:
                errors.append(pair_label)
                failed_sources.add(source_id)
                print(f"  {pair_label}: ERROR - {e}")

    # Phase 3: persist tokens only for sources whose pairs all succeeded.
    # Idempotent reconciliation means replaying a delta on retry is safe.
    for source_id, delta in deltas_by_source.items():
        if source_id in failed_sources:
            continue
        new_token = delta["new_token"]
        if not new_token:
            continue
        baseline_at = (
            now.isoformat() if delta["was_baseline"]
            else (delta["prior_baseline_at"] or now.isoformat())
        )
        token_store[source_id] = {"token": new_token, "baseline_at": baseline_at}

    try:
        save_token_store(token_store)
    except OSError as e:
        print(f"  Warning: could not persist token cache ({e})")

    print()
    print(f"Totals: +{total_created} created, ~{total_updated} updated, -{total_deleted} deleted")
    if errors:
        print(f"Errors in {len(errors)} step(s): {', '.join(errors)}")
        sys.exit(1)
    else:
        print("Sync completed successfully.")


if __name__ == "__main__":
    main()
