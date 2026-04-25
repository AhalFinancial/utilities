from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = "1"


@dataclass
class Session:
    session_id: str
    source_path: str
    source_name: str
    created_at: str
    session_dir: str
    source_hash: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "source_path": self.source_path,
            "source_name": self.source_name,
            "created_at": self.created_at,
            "session_dir": self.session_dir,
            "source_hash": self.source_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            session_id=data["session_id"],
            source_path=data["source_path"],
            source_name=data["source_name"],
            created_at=data["created_at"],
            session_dir=data["session_dir"],
            source_hash=data.get("source_hash"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


@dataclass
class RunMetadata:
    session_id: str
    started_at: str
    finished_at: Optional[str]
    tool_version: str
    model_name: Optional[str]
    cost_usd: Optional[float]
    summary_paths: Optional[dict] = None
    ingest_metadata: Optional[dict] = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tool_version": self.tool_version,
            "model_name": self.model_name,
            "cost_usd": self.cost_usd,
            "summary_paths": self.summary_paths or {},
            "ingest_metadata": self.ingest_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunMetadata":
        return cls(
            session_id=data["session_id"],
            started_at=data["started_at"],
            finished_at=data.get("finished_at"),
            tool_version=data.get("tool_version", "0.1.0"),
            model_name=data.get("model_name"),
            cost_usd=data.get("cost_usd"),
            summary_paths=data.get("summary_paths", {}),
            ingest_metadata=data.get("ingest_metadata"),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
