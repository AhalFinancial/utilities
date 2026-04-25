# utilities

Internal CLI utilities for AHAL Financial. Two packages:

- **`transcribe/`** — video/audio transcription with summarization, live recording, and PDF export
- **`calendarsync/`** — multi-account Google Calendar sync (cron-driven via GitHub Actions)

---

## transcribe (v0.2.0)

CLI for transcribing video/audio to text using `faster-whisper`, with optional GPT summarization, live recording, and PDF export.

### Features

- Transcribe local video/audio files (MP4, MKV, WebM, AVI, MP3, WAV, M4A, etc.)
- Live recording from microphone + system audio
- Auto language detection (Spanish / English)
- Chunked parallel transcription with checkpoint/resume
- GPT summarization with multiple styles: `executive`, `action-items`, `detailed`, `process-mapping`
- External context injection (file, inline text, or directory)
- Session-based output organized under `sessions/YYYY-MM/<timestamp>-<slug>/`
- Optional PDF export of the markdown output

### System requirements

**FFmpeg** must be installed and on `PATH`.

| Platform        | Install                                                                 |
| --------------- | ----------------------------------------------------------------------- |
| macOS           | `brew install ffmpeg`                                                   |
| Ubuntu/Debian   | `sudo apt-get install ffmpeg`                                           |
| Windows         | Download from https://ffmpeg.org/download.html and add `bin/` to `PATH` |

Verify: `ffmpeg -version`

For summarization, set `OPENAI_API_KEY` in your environment.

### Installation

```bash
pip install -e .
# Optional extras:
pip install -e ".[pdf]"     # PDF export (markdown + weasyprint)
pip install -e ".[record]"  # Live recording (sounddevice)
pip install -e ".[dev]"     # Test dependencies
```

### Usage

```bash
# Transcribe a file (default subcommand)
transcribe file meeting.mp4

# Transcribe + skip summary
transcribe file meeting.mp4 --no-summary

# Force a specific summary style
transcribe file meeting.mp4 --style action-items

# Inject external context (project glossary, attendee list, etc.)
transcribe file meeting.mp4 --context-file context.md

# Live recording
transcribe record

# Export PDF alongside markdown
transcribe file meeting.mp4 --pdf

# Diagnostics
transcribe check
```

Run `transcribe --help` for the full option list.

### Output

Sessions are stored under `sessions/YYYY-MM/<timestamp>-<slug>/`:

- `transcript.md` — full transcription with timestamps
- `notes.md` — summarization output (style-dependent)
- `session.json` — metadata (model, cost, schema version, ingest info)
- `transcript.pdf` / `notes.pdf` — when `--pdf` is set

Use `--legacy` to also write outputs next to the source file (pre-v0.2 behavior).

### Tests

```bash
.venv/Scripts/python -m pytest transcribe/tests/ -x
```

---

## calendarsync

Syncs busy blockers across multiple Google Calendars (rutopia, ahal, reurbano, personal). OAuth-per-account via `calendarsync/credentials/`. Driven by GitHub Actions on a 30-minute cron.

See `calendarsync/config.yaml` and `calendarsync/sync.py`.
