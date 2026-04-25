from dataclasses import dataclass
from typing import List, Optional

from .session import SCHEMA_VERSION


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "start": self.start,
            "end": self.end,
            "probability": self.probability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordTimestamp":
        return cls(
            word=data["word"],
            start=data["start"],
            end=data["end"],
            probability=data.get("probability"),
        )


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    avg_logprob: Optional[float] = None
    words: Optional[List[WordTimestamp]] = None

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "avg_logprob": self.avg_logprob,
            "words": [w.to_dict() for w in (self.words or [])],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptSegment":
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"],
            avg_logprob=data.get("avg_logprob"),
            words=[WordTimestamp.from_dict(w) for w in data.get("words", [])],
        )


@dataclass
class TranscriptArtifact:
    session_id: str
    source_path: str
    language: Optional[str]
    language_probability: Optional[float]
    duration: Optional[float]
    model_name: Optional[str]
    confidence_pct: Optional[float]
    quality_gate: Optional[dict]
    segments: List[TranscriptSegment]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "source_path": self.source_path,
            "language": self.language,
            "language_probability": self.language_probability,
            "duration": self.duration,
            "model_name": self.model_name,
            "confidence_pct": self.confidence_pct,
            "quality_gate": self.quality_gate,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptArtifact":
        return cls(
            session_id=data["session_id"],
            source_path=data["source_path"],
            language=data.get("language"),
            language_probability=data.get("language_probability"),
            duration=data.get("duration"),
            model_name=data.get("model_name"),
            confidence_pct=data.get("confidence_pct"),
            quality_gate=data.get("quality_gate"),
            segments=[TranscriptSegment.from_dict(s) for s in data.get("segments", [])],
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
