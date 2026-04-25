import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def slugify(value: str, max_len: int = 40) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if not value:
        value = "session"
    return value[:max_len]


def now_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


def year_month_from_timestamp(ts: str) -> str:
    return ts[:6].replace("-", "")


def session_id_for(source_path: str, timestamp: str) -> str:
    h = hashlib.sha256()
    h.update(source_path.encode("utf-8"))
    h.update(timestamp.encode("utf-8"))
    return h.hexdigest()[:12]


def sessions_root(base_dir: Optional[Path] = None) -> Path:
    base = base_dir or Path.cwd()
    return base / "sessions"


def session_folder_name(timestamp: str, source_name: str) -> str:
    return f"{timestamp}-{slugify(source_name)}"


def session_dir(
    base_dir: Path,
    timestamp: str,
    source_name: str,
) -> Path:
    ym = f"{timestamp[:4]}-{timestamp[4:6]}"
    return sessions_root(base_dir) / ym / session_folder_name(timestamp, source_name)
