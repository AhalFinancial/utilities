"""Live transcription manager for chunked recording."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, Optional

from transcribe.parallel import deduplicate_overlap
from transcribe.storage import json_store
from transcribe.transcriber import Transcriber


class LiveTranscriptionManager:
    """Streams chunk transcripts to disk while recording is still running."""

    def __init__(
        self,
        session_dir: Path,
        transcriber: Optional[Transcriber] = None,
        executor_workers: int = 1,
        status_callback: Optional[Callable[[Dict], None]] = None,
    ):
        self.session_dir = Path(session_dir)
        self._transcriber = transcriber or Transcriber()
        self._executor = ThreadPoolExecutor(max_workers=max(1, executor_workers))
        self._status_callback = status_callback
        self._prev_text = ""
        self._futures = set()
        self._shutdown = False
        self._entries = []

    @property
    def json_path(self) -> Path:
        return self.session_dir / "live_transcript.json"

    @property
    def md_path(self) -> Path:
        return self.session_dir / "live_transcript.md"

    def queue_chunk(
        self,
        chunk_index: int,
        mic_path: Path,
        loop_path: Path,  # retained for future uses
        start_seconds: float,
        duration_seconds: float,
    ) -> None:
        if self._shutdown:
            return

        future = self._executor.submit(
            self._transcribe_chunk,
            chunk_index,
            mic_path,
            start_seconds,
            duration_seconds,
        )
        self._futures.add(future)
        future.add_done_callback(self._handle_result)
        future.add_done_callback(lambda fut: self._futures.discard(fut))

    def _transcribe_chunk(
        self,
        chunk_index: int,
        mic_path: Path,
        start_seconds: float,
        duration_seconds: float,
    ) -> Dict:
        segments, info, confidence_pct = self._transcriber.transcribe_with_quality(
            mic_path, word_timestamps=True
        )
        text = " ".join(seg.text for seg in segments if getattr(seg, "text", "").strip())
        return {
            "chunk_idx": chunk_index,
            "text": text,
            "duration_seconds": duration_seconds,
            "start_seconds": start_seconds,
            "confidence_pct": confidence_pct,
        }

    def _handle_result(self, future) -> None:
        try:
            entry = future.result()
        except Exception as exc:  # pragma: no cover - runtime guard
            return

        raw_text = entry["text"]
        deduped = deduplicate_overlap(self._prev_text, raw_text)
        self._prev_text = raw_text
        entry["transcript"] = deduped or raw_text
        entry["snippet"] = entry["transcript"][:120]

        json_store.append_live_transcript_entry(self.session_dir, entry)
        json_store.append_live_transcript_md(self.session_dir, entry)
        self._entries.append(entry)

        if self._status_callback:
            self._status_callback(entry)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._executor.shutdown(wait=True)

    def metadata(self) -> Dict:
        return {
            "live_transcript_json": str(self.json_path),
            "live_transcript_md": str(self.md_path),
            "live_chunks_transcribed": len(self._entries),
        }
