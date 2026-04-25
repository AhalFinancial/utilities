"""Recording helpers for live sessions."""

from __future__ import annotations

import time
import wave
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


def _require_sounddevice(sd_module=None):
    if sd_module is not None:
        return sd_module
    try:
        import sounddevice as sd  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency check only
        raise RuntimeError(
            "sounddevice is required for live recording. Install with `pip install sounddevice`."
        ) from exc
    return sd


def _require_numpy(np_module=None):
    if np_module is not None:
        return np_module
    try:
        import numpy as np  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency check only
        raise RuntimeError("numpy is required for live recording.") from exc
    return np


def _write_wav(path: Path, data, sample_rate: int) -> None:
    np = _require_numpy()
    arr = data
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    pcm = np.clip(arr, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    channels = arr.shape[1]
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


@dataclass
class RecordingResult:
    chunk_paths: List[Path]
    started_at: float
    finished_at: float

    @property
    def duration(self) -> float:
        return max(0.0, self.finished_at - self.started_at)


def _pick_channel_count(device: Dict, *, is_loopback: bool) -> int:
    key = "max_output_channels" if is_loopback else "max_input_channels"
    available = device.get(key, 0)
    if available and available > 0:
        return available
    return min(max(1, available or 1), 2)


class _FrameBuffer:
    def __init__(self, np_module):
        self._buffers = deque()
        self._frames = 0
        self._lock = threading.Lock()
        self._np = np_module

    def append(self, data):
        with self._lock:
            self._buffers.append(data.copy())
            self._frames += data.shape[0]

    def available(self, count: int) -> bool:
        with self._lock:
            return self._frames >= count

    def consume(self, count: int):
        parts = []
        with self._lock:
            if self._frames < count:
                return None
            needed = count
            while needed > 0:
                chunk = self._buffers[0]
                if chunk.shape[0] <= needed:
                    parts.append(chunk)
                    needed -= chunk.shape[0]
                    self._frames -= chunk.shape[0]
                    self._buffers.popleft()
                else:
                    parts.append(chunk[:needed])
                    self._buffers[0] = chunk[needed:].copy()
                    self._frames -= needed
                    needed = 0
        return self._np.concatenate(parts, axis=0)


def _find_stereo_mix_device(sd_module) -> Optional[Dict]:
    hostapis = {idx: info.get("name") for idx, info in enumerate(sd_module.query_hostapis())}
    keywords = ("stereo mix", "what u hear", "wave out mix", "loopback")
    for dev in sd_module.query_devices():
        if dev.get("max_input_channels", 0) <= 0:
            continue
        name_lower = (dev.get("name") or "").lower()
        if any(keyword in name_lower for keyword in keywords):
            return {
                "index": dev["index"],
                "name": dev["name"],
                "hostapi": hostapis.get(dev["hostapi"]),
                "max_input_channels": dev.get("max_input_channels", 0),
                "max_output_channels": dev.get("max_input_channels", 0),
                "loopback": True,
                "label": f"{dev['name']} (capture)",
            }
    return None


def record_session(
    session_dir: Path,
    mic_device: Dict,
    loopback_device: Dict,
    sample_rate: int = 48000,
    chunk_duration: float = 2.0,
    max_seconds: Optional[float] = None,
    sd_module=None,
    chunk_callback: Optional[Callable[[int, Path, Path, float, float], None]] = None,
) -> RecordingResult:
    sd = _require_sounddevice(sd_module)
    np_module = _require_numpy()

    chunks_dir = Path(session_dir) / "chunks"
    mic_dir = chunks_dir / "mic"
    loop_dir = chunks_dir / "desktop"
    mic_dir.mkdir(parents=True, exist_ok=True)
    loop_dir.mkdir(parents=True, exist_ok=True)

    frames_per_chunk = int(sample_rate * chunk_duration)
    chunk_paths: List[Path] = []
    start_time = time.time()
    chunk_idx = 0
    elapsed_frames = 0

    wasapi_settings = None
    try:
        if loopback_device.get("hostapi") and "WASAPI" in loopback_device["hostapi"].upper():
            settings = sd.WasapiSettings()
            setattr(settings, "loopback", True)
            wasapi_settings = settings
    except Exception:
        wasapi_settings = None

    def _should_stop() -> bool:
        if max_seconds is None:
            return False
        return (time.time() - start_time) >= max_seconds

    mic_channels = _pick_channel_count(mic_device, is_loopback=False)
    loop_channels = _pick_channel_count(loopback_device, is_loopback=True)

    def _ensure_loopback_device():
        try:
            sd.check_input_settings(
                device=loopback_device["index"],
                channels=loop_channels,
                samplerate=sample_rate,
                extra_settings=wasapi_settings,
            )
            return loopback_device, loop_channels, wasapi_settings
        except Exception:
            fallback = _find_stereo_mix_device(sd)
            if fallback:
                fallback_channels = _pick_channel_count(fallback, is_loopback=True)
                return fallback, fallback_channels, None
            raise

    loopback_device, loop_channels, wasapi_settings = _ensure_loopback_device()

    mic_buffer = _FrameBuffer(np_module)
    loop_buffer = _FrameBuffer(np_module)

    def _callback(buffer):
        def _inner(indata, frames, time_info, status):
            if status:
                pass
            buffer.append(indata)

        return _inner

    mic_callback = _callback(mic_buffer)
    loop_callback = _callback(loop_buffer)

    with sd.InputStream(
        device=mic_device["index"],
        channels=mic_channels,
        samplerate=sample_rate,
        callback=mic_callback,
    ) as mic_stream, sd.InputStream(
        device=loopback_device["index"],
        channels=loop_channels,
        samplerate=sample_rate,
        callback=loop_callback,
        extra_settings=wasapi_settings,
    ) as loop_stream:
        try:
            while True:
                if _should_stop():
                    break
                if mic_buffer.available(frames_per_chunk) and loop_buffer.available(frames_per_chunk):
                    mic_data = mic_buffer.consume(frames_per_chunk)
                    loop_data = loop_buffer.consume(frames_per_chunk)
                    mic_path = mic_dir / f"mic_{chunk_idx:04d}.wav"
                    loop_path = loop_dir / f"desktop_{chunk_idx:04d}.wav"
                    _write_wav(mic_path, mic_data, sample_rate)
                    _write_wav(loop_path, loop_data, sample_rate)
                    chunk_paths.extend([mic_path, loop_path])
                    frames_written = mic_data.shape[0]
                    chunk_start_sec = elapsed_frames / sample_rate
                    chunk_duration_sec = frames_written / sample_rate
                    elapsed_frames += frames_written
                    if chunk_callback is not None:
                        chunk_callback(
                            chunk_idx,
                            mic_path,
                            loop_path,
                            chunk_start_sec,
                            chunk_duration_sec,
                        )
                    chunk_idx += 1
                else:
                    time.sleep(0.01)
        except KeyboardInterrupt:
            pass

    finished = time.time()
    return RecordingResult(chunk_paths=chunk_paths, started_at=start_time, finished_at=finished)
