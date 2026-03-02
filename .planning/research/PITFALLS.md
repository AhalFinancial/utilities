# Domain Pitfalls

**Domain:** Video transcription and summarization CLI tools
**Researched:** 2026-03-02
**Confidence:** MEDIUM

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Naive Chunking Breaking Context Mid-Sentence

**What goes wrong:**
The transcription API (Whisper, etc.) has file size limits (25MB for Whisper). Developers split audio files at arbitrary points (e.g., every N MB) without considering sentence/phrase boundaries. This causes loss of context between chunks, resulting in fragmented transcripts with missing words, incorrect punctuation, and poor accuracy at chunk boundaries.

**Why it happens:**
File size limits force chunking, but audio waveforms don't have natural "split points" like text documents. Developers default to simple time-based or size-based splits without analyzing audio content.

**Consequences:**
- Transcript accuracy drops 10-30% at chunk boundaries
- Speaker context lost between chunks (diarization fails)
- Timestamps become misaligned requiring complex recalculation
- Summary quality degrades due to incomplete sentences
- User trust erodes when reviewing obviously broken transcripts

**Prevention:**
- Use silence detection to find natural break points between sentences
- Implement overlapping chunks (5-10 seconds) and deduplicate results
- Pass previous chunk's transcript as context/prompt to next chunk (Whisper supports this)
- Store segment timestamps and adjust to global timeline (+= chunk_start_time)
- Never chunk mid-word or mid-sentence

**Detection:**
- Review chunk boundaries in test files - do they align with pauses?
- Check if accuracy degrades in middle sections of long files
- Look for repeated phrases at chunk transitions
- Monitor for punctuation errors after timestamp adjustments

**Phase to address:**
Phase 1 (Audio Processing) - Implement smart chunking before transcription. Test with 3+ hour videos.

---

### Pitfall 2: Ignoring Whisper Hallucinations on Long/Repetitive Audio

**What goes wrong:**
Whisper (and other ASR models) start "hallucinating" on long videos - repeating the same phrase endlessly or generating completely fabricated text unrelated to the audio. This commonly occurs after 4-8 minutes on the large model, especially with low audio quality, silence, or repetitive background music.

**Why it happens:**
Whisper's attention mechanism can get "stuck" on patterns in long sequences. Background music, ambient noise, or extended silence triggers the model to fill gaps with plausible-sounding but incorrect text. The model was primarily trained on shorter audio segments.

**Consequences:**
- Transcripts 2-3x longer than actual speech content
- Completely fabricated content appears authoritative
- Summaries include hallucinated information
- User wastes time reviewing garbage transcripts
- Credibility destroyed when users notice repeated nonsense

**Prevention:**
- Enable Voice Activity Detection (VAD) in transcription settings to skip silence
- Use Whisper's `condition_on_previous_text=False` to prevent repetition loops
- Implement hallucination detection: check for repeated n-grams (if same 10+ words repeat 3+ times, flag it)
- Use `temperature=0` for more deterministic output
- Consider using Whisper-large-v3-turbo instead of older models (better long-form performance)
- Split audio at natural breaks (detected silence) rather than forcing full-length processing

**Detection:**
- Search transcripts for repeated phrases (regex: `(.{20,})\1{2,}`)
- Calculate transcript length vs audio duration ratio (flag if >1.5x expected)
- Review transcripts of silent sections - should be minimal/empty
- Test with background music videos - common hallucination trigger

**Phase to address:**
Phase 1 (Transcription) - Add hallucination detection and VAD before MVP. Test with meeting recordings containing silence.

---

### Pitfall 3: Assuming Auto Language Detection Works Reliably

**What goes wrong:**
Project requires Spanish/English auto-detection. Whisper and other STT models often misidentify language, especially with: (1) code-switching (Spanish speaker inserts English terms), (2) accented Spanish, (3) short audio clips, (4) proper nouns. The model either translates everything to English despite `task='transcribe'` or outputs wrong language entirely.

**Consequences:**
- English words in Spanish speech get translated/corrupted
- Spanish transcripts output in English despite source being Spanish
- Technical terms and proper nouns mangled beyond recognition
- Summary references wrong language content
- Accuracy drops 20-40% on multilingual content

**Prevention:**
- **Never rely on auto-detection alone** - provide language hint if detectable from metadata
- Use `language='es'` or `language='en'` parameter when confidence >70%
- Implement post-detection validation: if specified Spanish but output is 80%+ English words, retry with English
- Use language detection library (langdetect, langid) on transcript to verify output matches expectation
- For code-switching: Whisper can handle if task='transcribe' + correct primary language specified
- Document limitation: tool may not handle code-switching perfectly - set user expectations

**Detection:**
- Run language detection on output transcript, compare to expected
- Test with real Spanish meeting recordings (not textbook Spanish)
- Test with Spanglish content (common in US/Latin America business contexts)
- Check if proper nouns (brands, names, places) survive transcription

**Phase to address:**
Phase 1 (Transcription) - Add language validation before summarization. Test with bilingual content early.

---

### Pitfall 4: Forgetting FFmpeg Codec Hell

**What goes wrong:**
Project supports mp4, mkv, webm input formats. FFmpeg extracts audio, but developers forget that containers (mp4) and codecs (H.264, VP9, opus) are separate. Audio extraction fails or produces corrupt output when:
- MKV contains opus codec → can't stream-copy to mp3
- FFmpeg version mismatch (FFmpeg 8.x incompatible with some libraries)
- Variable frame rate videos cause audio sync issues
- Multiple audio tracks in video (which one to extract?)

**Consequences:**
- Tool silently fails on 15-25% of real-world videos
- Audio/transcript timestamps misaligned (unusable for sync)
- Corrupt audio files crash transcription API
- "Works on my machine" but fails on user systems with different FFmpeg versions

**Prevention:**
- Always re-encode audio to consistent format (e.g., wav 16kHz mono) - don't use `-acodec copy`
- Use `-avoid_negative_ts make_zero` to prevent timestamp issues
- Detect multiple audio tracks, let user choose or default to first track
- Pin FFmpeg version requirement (e.g., 7.x) in docs/installation
- Test with diverse codec zoo: H.264/AAC, VP9/opus, HEVC/opus, old codecs (MPEG-2)
- Handle FFmpeg stderr output - it's chatty but contains critical errors

**Detection:**
- Test suite must include videos with: MKV/opus, webm/VP9, variable frame rate, multi-track audio
- Check extracted audio duration matches video duration
- Verify timestamps align (play video + transcript side-by-side)
- Monitor FFmpeg exit codes (non-zero = failure, don't proceed)

**Phase to address:**
Phase 1 (Audio Extraction) - Build robust FFmpeg wrapper with error handling and format normalization from start.

---

### Pitfall 5: Not Planning for API Rate Limits and Failures

**What goes wrong:**
Whisper API has 25MB file limit. Claude API has rate limits (RPM, tokens per minute). Developers build happy-path code that works on first test file, then tool crashes on:
- Whisper API 429 rate limit (too many chunks submitted too fast)
- Claude API 429 rate limit (transcript too large, summarization fails)
- Transient network failures (timeout, connection reset)
- API returns 5xx error during processing

**Consequences:**
- Tool fails halfway through 2-hour video, loses all progress
- No retry logic → user must restart from scratch
- Claude summarization fails silently → no summary output
- User loses money on API calls for partial/failed processing

**Prevention:**
- **Implement exponential backoff with jitter** for all API calls (use `tenacity` library)
- Retry only transient errors (429, 5xx, timeouts) - fail fast on 4xx validation errors
- Max 3-5 retry attempts with cap at 30 seconds between retries
- For Claude API: chunk large transcripts if >100K tokens (check token count before sending)
- Save intermediate results: transcription chunks to disk, reload on failure
- Implement progress tracking: show "Processing chunk 5/12" so users know it's not frozen
- Use prompt caching for Claude API (reduces token count for rate limits)

**Detection:**
- Simulate rate limits in tests (mock API returns 429)
- Test with 3-hour video requiring 15+ API calls
- Kill network mid-processing, verify graceful degradation
- Check if partial results are saved and resumable

**Phase to address:**
Phase 1 (Core Processing) - Build retry logic and progress tracking before handling large files.

---

### Pitfall 6: Summarization Hallucinations from Poor Transcripts

**What goes wrong:**
Developers treat transcription and summarization as independent steps. Garbage transcript → garbage summary, but LLM (Claude) generates fluent, authoritative-sounding summaries even when source transcript is 50% hallucinated/incorrect. Users can't tell the summary is fabricated.

**Why it happens:**
LLMs are trained to produce coherent text even with poor inputs. Transcription errors (homophones, missing words, speaker misattribution) aren't flagged, so LLM summarizes confidently. Developers don't validate transcript quality before summarization.

**Consequences:**
- Summaries include completely fabricated information
- Critical details omitted because transcription missed them
- Speaker attribution wrong (Alice's comments attributed to Bob)
- User makes decisions based on incorrect summary
- Legal/compliance risk if used for meeting minutes

**Prevention:**
- **Quality gate between transcription and summarization:**
  - Calculate confidence scores (if API provides them)
  - Check for hallucination patterns (repeated phrases)
  - Validate speaker count matches expected
- Prompt Claude to flag low-confidence sections: "Note any unclear sections as [UNCLEAR]"
- Include transcript excerpts in summary output so users can verify claims
- Provide both full transcript and summary (not just summary)
- Document limitation: "Summary quality depends on audio quality - review transcript for critical use"

**Detection:**
- Compare summary claims to transcript source - are all facts grounded?
- Test with deliberately poor audio (background noise, multiple speakers)
- Review summaries for phrases not present in transcript
- Use multiple reviewers to identify hallucinated content

**Phase to address:**
Phase 2 (Summarization) - Add quality validation before sending to Claude. Include uncertainty markers.

---

### Pitfall 7: Temporary File Cleanup Failures

**What goes wrong:**
Tool extracts audio from video to temp file, transcribes, then summarizes. Developers forget to clean up temp files, resulting in:
- Disk fills up after processing 10-20 videos (3+ hour videos = multi-GB audio files)
- Orphaned files when tool crashes mid-processing
- Temp files persist across restarts
- Windows locks temp files if handles not closed properly

**Why it happens:**
Python's `tempfile` module helps but doesn't guarantee cleanup on crashes. Developers forget to use `try/finally` or context managers. Long-running processes accumulate files.

**Consequences:**
- User's disk fills up, system becomes unstable
- Temp folder contains sensitive audio/transcripts (privacy issue)
- Tool crashes due to out-of-disk-space mid-processing
- User must manually find and delete orphaned files

**Prevention:**
- Use `tempfile.TemporaryDirectory()` context manager - auto-cleanup on exit
- Wrap all temp file operations in `try/finally` to ensure cleanup
- Set temp file prefix for easy identification (`temp_videotranscribe_`)
- Add cleanup on startup: delete all `temp_videotranscribe_*` files from previous runs
- Monitor disk space before extraction: if <5GB available, warn user
- Provide `--keep-temp` debug flag (default: delete)
- Use platform-specific temp dirs (`tempfile.gettempdir()`)

**Detection:**
- Process 5 videos, check temp directory - should be empty
- Kill process mid-processing, restart, check for orphaned files
- Run on system with limited disk space, verify graceful handling
- Check file handle cleanup (no locked files after processing)

**Phase to address:**
Phase 1 (Audio Extraction) - Implement robust temp file management from start.

---

## Moderate Pitfalls

### Pitfall 1: No Progress Indication for Long Videos

**What goes wrong:**
User runs tool on 3-hour video. CLI prints nothing for 20 minutes. User assumes it's frozen and kills process.

**Prevention:**
- Print progress messages: "Extracting audio...", "Processing chunk 3/12 (25%)", "Generating summary..."
- Use progress bar library (`tqdm`) for chunk processing
- Estimate time remaining based on audio duration (rough: 1 min audio = 10-20 sec processing)
- Flush stdout to ensure messages appear immediately: `print(..., flush=True)`

---

### Pitfall 2: Missing Speaker Labels in Meeting Transcripts

**What goes wrong:**
Meeting recordings have 3-5 speakers. Transcript is wall of text without speaker identification. Summary attributes comments to wrong people or can't identify who said what.

**Prevention:**
- Implement speaker diarization (pyannote.audio, AssemblyAI API, or Whisper with diarization)
- Document accuracy limitation: 80-95% depending on audio quality, drops significantly with overlapping speech
- Ensure speakers talk for 30+ seconds uninterrupted for best results
- Format output with speaker labels: "Speaker 1: [text]"
- Validate timestamps don't drift between diarization and transcription

---

### Pitfall 3: Output File Overwrites Without Warning

**What goes wrong:**
User runs tool twice on same video. Second run silently overwrites transcript/summary from first run. User loses manual edits or previous version.

**Prevention:**
- Check if output file exists before writing
- Prompt user: "Output file exists. Overwrite? (y/n)" or use `--force` flag
- Alternative: append timestamp to filename (`video_transcript_20260302_143022.txt`)
- Provide `--output` flag to specify custom output path

---

### Pitfall 4: Hardcoded Paths and OS-Specific Issues

**What goes wrong:**
Developers code on Windows, use backslashes in paths. Tool breaks on Linux/Mac. FFmpeg binary name differs (ffmpeg.exe vs ffmpeg). Temp directory paths hardcoded.

**Prevention:**
- Use `pathlib.Path` for all path operations (cross-platform)
- Use `shutil.which('ffmpeg')` to find FFmpeg binary
- Never hardcode temp paths - use `tempfile.gettempdir()`
- Test on Windows, Linux, and Mac (or use CI matrix)

---

### Pitfall 5: No Input Validation

**What goes wrong:**
User passes text file instead of video. Tool crashes with cryptic FFmpeg error. User doesn't know what went wrong.

**Prevention:**
- Validate file exists before processing
- Check file extension against allowed list (mp4, mkv, webm, avi, mov)
- Verify file is readable and not empty (size > 0)
- Provide clear error messages: "Error: 'file.txt' is not a valid video format. Supported: mp4, mkv, webm"

---

## Minor Pitfalls

### Pitfall 1: API Keys in Code or Logs

**What goes wrong:**
Developer hardcodes Claude API key for testing, commits to git. Key appears in error messages/logs.

**Prevention:**
- Load API keys from environment variables only
- Add `.env` to `.gitignore`
- Redact keys in error messages: `api_key[:8] + '...'`
- Document key setup in README

---

### Pitfall 2: No Cost Estimation

**What goes wrong:**
User transcribes 20 hours of video, receives $50 API bill, was not expecting cost.

**Prevention:**
- Calculate estimated cost before processing: (audio minutes * $0.006) + (tokens * $0.015/1K)
- Print estimate: "Estimated cost: $2.50 (Whisper) + $0.80 (Claude) = $3.30"
- Require confirmation for videos >1 hour or estimated cost >$5

---

### Pitfall 3: Unclear Output Format

**What goes wrong:**
Tool outputs plain text. User wants markdown, JSON, or SRT subtitles. Format not documented.

**Prevention:**
- Document output format in README and `--help`
- Provide `--format` flag: txt, md, json, srt
- Default to markdown (readable + structured)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skipping error handling on API calls | Faster initial development | Tool crashes on transient failures, users lose progress | Never - implement retries from start |
| Using `os.system()` instead of `subprocess` for FFmpeg | Simpler code | Can't capture errors, security risk (shell injection), not cross-platform | Never - always use subprocess |
| No logging, only print statements | Less boilerplate | Impossible to debug user issues, can't control verbosity | Only for MVP prototype, add logging in Phase 1 |
| Hardcoding Whisper model (`whisper-1`) | Works now | Can't upgrade to better models without code changes | Acceptable if exposed as CLI flag |
| Inline prompts instead of templates | Faster iteration | Hard to test, version, and improve prompts | Acceptable for MVP, refactor to templates in Phase 2 |
| Synchronous processing only | Simpler code | Can't process multiple files in parallel | Acceptable for MVP (single-file use case) |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Whisper API | Sending raw video file instead of extracted audio | Always extract audio first (FFmpeg), send audio only |
| Whisper API | Not setting `language` parameter | Specify language if known, improves accuracy 10-20% |
| Claude API | Sending entire transcript in single message | Check token count first, chunk if >100K tokens, use prompt caching for long context |
| Claude API | Not handling streaming responses | Use streaming for better UX on long summaries (show progress) |
| FFmpeg | Not checking exit code | Always check `returncode != 0`, parse stderr for errors |
| FFmpeg | Using `-c copy` (stream copy) | Re-encode audio to consistent format to avoid codec issues |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading entire audio file into memory | Works for 5-min videos | Stream audio processing, use generators | Videos >500MB (30+ min at high quality) |
| Processing video without checking duration first | Fast for short videos | Check duration, warn if >2 hours, estimate processing time | Videos >2 hours (10+ min processing) |
| Synchronous API calls for chunked audio | Works for 2-3 chunks | Use async/concurrent requests (with rate limit respect) | Videos requiring 10+ chunks (30+ min audio) |
| Keeping all transcription chunks in memory | Works for <10 chunks | Write chunks to disk immediately, stream to Claude | Videos >1 hour (15+ chunks) |
| Not caching language detection results | Negligible delay | Cache detection result for reuse in summary prompt | Multiple operations on same file |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Not sanitizing video filenames in output paths | Path traversal attack (`../../etc/passwd.mp4`) | Use `os.path.basename()`, validate filename, never use user input directly in paths |
| Logging full transcripts containing PII | Privacy violation, GDPR issues | Truncate logs, redact PII, or disable transcript logging |
| Storing API keys in code or version control | Key exposure, unauthorized usage | Use environment variables, .env files (gitignored), never commit keys |
| Processing videos from untrusted sources without validation | Malicious video exploits FFmpeg vulnerability | Validate file format, size limits, consider sandboxing FFmpeg |
| Including sensitive meeting content in error reports | Data leak | Sanitize error messages, don't include transcript excerpts in exceptions |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No indication of processing time | User doesn't know if 30 min wait is normal | Show progress, estimate time remaining based on duration |
| Cryptic FFmpeg errors passed to user | User has no idea what "codec not supported" means | Translate technical errors to user-friendly messages |
| Requiring manual API key configuration in code | Friction, error-prone | Use `.env` file or interactive prompt on first run |
| No way to cancel long-running job | User stuck waiting, must kill process | Implement signal handling (Ctrl+C gracefully stops and cleans up) |
| Output only summary, not transcript | User can't verify summary accuracy | Always output both, or make configurable |
| No indication of API costs | User surprised by bill | Show estimated cost before processing, require confirmation |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Transcription works:** Often missing - VAD (silence handling), hallucination detection, verify with 30+ min video with silence
- [ ] **Chunking implemented:** Often missing - context preservation between chunks, timestamp recalculation, verify boundaries don't break mid-sentence
- [ ] **Language detection:** Often missing - validation that output matches expected language, verify with bilingual content
- [ ] **Error handling:** Often missing - retry logic with exponential backoff, verify by simulating API failures
- [ ] **Progress indication:** Often missing - progress bar or status messages, verify with 1+ hour video
- [ ] **Cleanup:** Often missing - temp file deletion on crash/failure, verify by killing process mid-run
- [ ] **Output format:** Often missing - speaker labels, timestamps, markdown formatting, verify with multi-speaker meeting
- [ ] **API cost estimation:** Often missing - calculate and display before processing, verify with long video
- [ ] **Cross-platform:** Often missing - test on Windows + Linux, verify paths and FFmpeg binary resolution
- [ ] **Input validation:** Often missing - file exists, correct format, readable, verify with invalid inputs

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Naive chunking broke context | MEDIUM | Re-process with improved chunking logic, may need manual transcript review |
| Whisper hallucinations | LOW | Re-run with VAD enabled and `condition_on_previous_text=False`, or use shorter chunks |
| Wrong language detected | LOW | Re-transcribe with explicit language parameter |
| FFmpeg codec issues | LOW | Re-extract audio with re-encoding (no stream copy), test with different output format |
| API rate limit exceeded | LOW | Automatic retry with backoff handles this, no manual intervention needed |
| Summarization hallucination | MEDIUM | Re-run with improved prompt (ask for citations), manual review of summary |
| Temp files fill disk | LOW | Manual cleanup, add disk space check before processing |
| Lost progress on failure | HIGH (if no checkpointing) | Must re-process from start, implement checkpoint saving to prevent |
| Corrupt audio extraction | LOW | Delete temp audio, re-extract with different codec settings |
| Multi-language mixing issues | MEDIUM | Split audio by language (manual or automatic), process separately, combine results |

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Audio Extraction | FFmpeg codec compatibility issues, temp file cleanup | Test diverse video formats, implement robust temp file handling with context managers |
| Phase 1: Chunking | Breaking context mid-sentence, timestamp misalignment | Use silence detection, implement overlap, test with long videos (3+ hours) |
| Phase 1: Transcription | Whisper hallucinations on long audio | Add VAD, hallucination detection, test with meetings containing silence |
| Phase 1: Language Detection | Auto-detection unreliable for code-switching | Add validation, allow manual override, test with bilingual content |
| Phase 1: Error Handling | No retry logic for API failures | Implement exponential backoff from start, test with simulated failures |
| Phase 2: Summarization | Hallucinations from poor transcript quality | Add quality gate, include grounding citations, provide both transcript and summary |
| Phase 2: Progress Tracking | No indication during long processing | Add progress messages and time estimates early |
| Phase 3: Output Formatting | Speaker labels missing or wrong | Implement diarization, validate accuracy, document limitations |
| Phase 3: Cost Management | No cost estimation for users | Calculate and display estimated cost before processing |

---

## Sources

**Audio Quality and Transcription Accuracy:**
- [Common Mistakes in Video Transcription: How to Avoid Them](https://www.spacedaily.com/reports/Common_Mistakes_in_Video_Transcription_How_to_Avoid_Them_999.html)
- [What Impacts AI Transcription Accuracy?](https://www.happyscribe.com/blog/what-impacts-ai-transcription-accuracy)
- [Why Your AI Transcription Is Wrong (Top Causes and Solutions)](https://gotranscript.com/en/blog/why-your-ai-transcription-is-wrong-top-causes-and-solutions)

**FFmpeg Audio Extraction Issues:**
- [How to extract audio from video files using FFmpeg | Mux](https://www.mux.com/articles/extract-audio-from-a-video-file-with-ffmpeg)
- [Extracting Audio From Video Files Using FFmpeg | Baeldung on Linux](https://www.baeldung.com/linux/ffmpeg-audio-from-video)
- [FFmpeg and TorchCodec Issues](https://deepwiki.com/0x0funky/audioghost-ai/11.2-ffmpeg-and-torchcodec-issues)

**Speech-to-Text Challenges:**
- [Top 7 Speech Recognition Challenges & Solutions in 2026](https://research.aimultiple.com/speech-recognition-challenges/)
- [AI Transcription Getting Words Wrong? 2026 Solutions](https://brasstranscripts.com/blog/ai-transcription-keeps-getting-words-wrong-2026-solutions)
- [Speech-to-Text Benchmark: Deepgram vs. Whisper](https://research.aimultiple.com/speech-to-text/)

**Whisper Hallucinations:**
- [Solutions to Repeated Output Issues with Whisper | Memo AI](https://memo.ac/blog/whisper-hallucinations)
- [mlx_whisper memory usage keeps growing](https://github.com/ml-explore/mlx-examples/issues/1254)

**Whisper API Best Practices:**
- [Questions regarding transcribing long audios (>25MB) in Whisper API](https://community.openai.com/t/questions-regarding-transcribing-long-audios-25mb-in-whisper-api/267384)
- [OpenAI Whisper in Practice (2026): From Raw Audio to Reliable Transcripts](https://thelinuxcode.com/openai-whisper-in-practice-2026-from-raw-audio-to-reliable-transcripts/)
- [How to Build a Long Audio Transcription Tool with OpenAI's Whisper API](https://www.buildwithmatija.com/blog/building-a-long-audio-transcription-tool-with-openai-s-whisper-api)
- [Speech to text | OpenAI API](https://platform.openai.com/docs/guides/speech-to-text)

**Multilingual Transcription:**
- [Multi-Language Audio and Transcription Inconsistencies](https://github.com/openai/whisper/discussions/2009)
- [Language Detection | Deepgram's Docs](https://developers.deepgram.com/docs/language-detection)

**API Limits:**
- [OpenAI Whisper API Limits: Transcribing Audio File Limits 2024](https://www.transcribetube.com/blog/openai-whisper-api-limits)
- [Rate limits - Claude API Docs](https://docs.claude.com/en/api/rate-limits)
- [Understanding usage and length limits | Claude Help Center](https://support.claude.com/en/articles/11647753-understanding-usage-and-length-limits)

**Summarization Hallucinations:**
- [A hallucination detection and mitigation framework for faithful text summarization using LLMs](https://www.nature.com/articles/s41598-025-31075-1)
- [Risk of AI hallucination in summarization](https://donets.org/risks/risk-of-ai-hallucination-in-summarization)

**Error Handling and Retry:**
- [Mastering Retry Mechanisms in Python: Real-Life Examples](https://medium.com/@oggy/retry-mechanisms-in-python-practical-guide-with-real-life-examples-ed323e7a8871)
- [GitHub - jd/tenacity: Retrying library for Python](https://github.com/jd/tenacity)
- [API Error Handling & Retry Strategies: Python Guide 2026](https://easyparser.com/blog/api-error-handling-retry-strategies-python-guide)

**Video Codec Compatibility:**
- [Resolving the "Video Codec Not Supported" Issue | Cloudinary](https://cloudinary.com/guides/front-end-development/video-codec-not-supported)
- [WebM Format: Basic Facts, Compatibility, and WebM vs. MP4](https://cloudinary.com/guides/video-formats/webm-format-what-you-should-know)
- [Web video codec guide - Media | MDN](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs)

**Speaker Diarization:**
- [12 Best Speaker Diarization Tools for Multi-Speaker Video](https://www.opus.pro/blog/best-speaker-diarization-tools-multi-speaker-video)
- [What is speaker diarization and how does it work? (Complete 2026 Guide)](https://www.assemblyai.com/blog/what-is-speaker-diarization-and-how-does-it-work)

**Progress Tracking:**
- [Logging & job progress](https://www.jobrunr.io/en/documentation/background-methods/logging-progress/)

---
*Pitfalls research for: Video transcription and summarization CLI tools*
*Researched: 2026-03-02*
