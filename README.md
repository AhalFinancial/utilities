# transcribe-tool

CLI tool for transcribing video to text using faster-whisper

## Description

Extract audio from video files, transcribe speech to text with accurate recognition. Supports Spanish and English audio with automatic language detection.

## System Requirements

**FFmpeg must be installed on your system before using this tool.**

### Installation by platform:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows:**
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract the archive
3. Add the `bin` folder to your system PATH

Verify installation:
```bash
ffmpeg -version
```

## Installation

Install the tool in editable mode:

```bash
pip install -e .
```

## Usage

Basic usage:
```bash
transcribe video.mp4
```

## Supported Video Formats

- MP4
- MKV
- WebM
- AVI

## Output

The tool creates a transcript file alongside your video:
- Input: `meeting.mp4`
- Output: `meeting_transcript.md`

Output includes:
- Full transcription with timestamps
- Metadata (file name, duration, language detected)
