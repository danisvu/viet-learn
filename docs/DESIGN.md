# VietLearn — Technical Design Document

> **Version:** 1.1 (includes PDF Lecture Notes feature)
> **Platform:** macOS — Mac Mini M4 (24GB RAM, 256GB SSD)
> **Framework:** Python 3.11 + PyQt6 — 100% Local/Offline

---

## 1. Project Overview

VietLearn translates English educational video content into Vietnamese. It processes videos from YouTube, DeepLearning.AI, and Udemy, producing translated subtitles (SRT), Vietnamese audio narration, and dubbed video files. All AI processing runs locally using open-source models.

### 1.1 Core Objectives
- Translate English video lectures to Vietnamese with high accuracy
- Generate Vietnamese audio narration synchronized with original video timeline
- Support three source platforms: YouTube, DeepLearning.AI, Udemy
- Run 100% offline on Mac Mini M4 (24GB unified memory, ~18GB available)
- Provide learning-enhancement features: glossary, summaries, flashcards, PDF notes

### 1.2 Target User
Vietnamese learner studying AI/ML, programming, and technical subjects from English-language online courses. Intermediate English proficiency — needs full translation, not just supplementary subtitles.

### 1.3 Hardware Constraints

| Spec | Detail |
|------|--------|
| Device | Mac Mini M4 |
| Total RAM | 24GB unified memory |
| Available RAM | ~18GB (OS uses ~6GB) |
| Storage | 256GB SSD |
| GPU | M4 integrated (Apple Silicon Metal) |

---

## 2. Platform-Specific Input Workflows

Each platform has a distinct method for obtaining video and subtitle content. All three converge into a shared processing pipeline after the input stage.

### 2.1 YouTube

**Input method:** Paste URL into app → yt-dlp auto-downloads everything

**Download command:**
```bash
yt-dlp -f "bestvideo+bestaudio" --merge-output-format mp4 \
  --write-subs --write-auto-subs --sub-lang en --convert-subs srt \
  -o "%(title)s.%(ext)s" URL
```

**Output files:**
- Video file (.mp4) with audio
- Subtitle file (.srt) — prioritizes creator subtitles over auto-generated
- If no SRT available: fallback to Whisper STT on downloaded audio

**Batch support:** Supports playlist URLs and queue of multiple videos for overnight processing.

### 2.2 DeepLearning.AI

**Input method:** User manually imports video file + VTT/SRT file into app

User downloads video and subtitle files externally, then imports both into VietLearn. The app accepts VTT format and automatically converts to SRT.

**Supported input formats:**
- Video: .mp4, .webm, .mkv
- Subtitle: .srt, .vtt (auto-converted to SRT)

### 2.3 Udemy

**Primary method (Plan A):** yt-dlp + browser cookies

```bash
yt-dlp --cookies-from-browser chrome \
  --referer "https://www.udemy.com/course/..." \
  --write-subs --sub-lang en --convert-subs srt URL
```

**Fallback method (Plan B):** BlackHole 2ch audio capture

If yt-dlp fails due to DRM encryption (HTTP 403), the app falls back to capturing system audio via BlackHole 2ch virtual audio device while the user watches the lecture. The recorded audio is then processed by Whisper STT. Output is SRT + Vietnamese audio only (no video merge).

---

## 3. Shared Processing Pipeline

After obtaining video and SRT from any platform, all content enters the same pipeline.

### 3.1 Pipeline Steps

1. **SRT Parsing** — Read SRT file, extract each subtitle entry with index, start time, end time, and English text.
2. **Translation** — Qwen3-8B (via Ollama) translates each subtitle entry from English to Vietnamese. Glossary terms are applied to maintain consistent technical vocabulary.
3. **SRT Generation** — Create bilingual SRT file (English + Vietnamese) and Vietnamese-only SRT file, preserving original timestamps.
4. **TTS Audio Generation** — Piper TTS generates Vietnamese audio for each subtitle entry.
5. **Time-Stretch Synchronization** — Each audio clip is stretched/compressed to fit its SRT time slot exactly.
6. **Audio Assembly** — All clips are placed at their correct timestamps in a single audio track matching the video duration.
7. **Video Merge (FFmpeg)** — Combine original video + original audio (reduced to 15-20% volume) + Vietnamese audio track into final .mp4 with dual audio tracks.

### 3.2 Time-Stretch Synchronization (Detail)

This is the critical step ensuring audio matches video timeline. For each SRT entry:

| Step | Description |
|------|-------------|
| Calculate slot duration | `end_time - start_time` from SRT (e.g. 3.5 seconds) |
| Generate TTS audio | Piper TTS reads Vietnamese text at normal speed |
| Measure TTS duration | e.g. 4.2 seconds |
| Calculate speed ratio | `TTS_duration / slot_duration` = 4.2 / 3.5 = 1.2x |
| Apply time-stretch | FFmpeg/librosa adjusts audio to exactly 3.5 seconds |
| Place in timeline | Audio clip starts at SRT `start_time` position |

**Speed limits:**
- Maximum speed-up: **1.6x** (faster makes speech unintelligible)
- Maximum slow-down: **0.75x** (slower sounds unnatural)
- If speed > 1.6x required: app warns user with options — accept fast speech, or use Qwen3 to summarize the translation shorter then re-generate TTS

**Gap handling:**
- Silence between SRT entries is preserved — no Vietnamese audio during gaps
- If TTS is shorter than slot: pad with silence at end of clip (no slow-down unless < 0.75x ratio)

---

## 4. AI Models & Resource Allocation

### 4.1 Model Stack

| Function | Model | Size | RAM | Speed |
|----------|-------|------|-----|-------|
| Speech-to-Text | Whisper large-v3-turbo (whisper.cpp) | ~1.5GB | ~2GB | ~10x realtime on M4 |
| Translation | Qwen3-8B Q4_K_M (Ollama) | ~5GB | ~6GB | ~15-20 tok/s on M4 |
| Text-to-Speech | Piper TTS + Vietnamese VITS | ~50MB | ~0.5GB | Faster than realtime |
| Summarize/Flashcard | Qwen3-8B (shared with translation) | — | — | Same instance |

### 4.2 RAM Budget

Models run sequentially (not simultaneously) during pipeline processing:

| Phase | Active Models | Peak RAM |
|-------|--------------|----------|
| STT Phase | Whisper only | ~2GB |
| Translation Phase | Qwen3-8B only | ~6GB |
| TTS Phase | Piper TTS only | ~0.5GB |
| Merge Phase | FFmpeg (no AI model) | ~0.3GB |
| App + OS overhead | — | ~6GB |
| **Maximum total at any time** | — | **~12GB (within 18GB)** |

### 4.3 Alternative Translation Models

- **Qwen3-30B-A3B** (MoE, Q4): ~18GB RAM, better quality, significantly slower
- **Qwen3.5-9B**: ~6.6GB RAM, newest model, slightly better than Qwen3-8B

---

## 5. Smart Glossary System

Technical terms require consistent handling across translations.

### 5.1 Glossary Modes

| Mode | Example Input | Example Output |
|------|--------------|----------------|
| Keep English | gradient descent | gradient descent |
| Translate + annotate | overfitting | hiện tượng học quá khớp (overfitting) |
| Replace | epoch | vòng huấn luyện |

### 5.2 Built-in Glossary Packs

- **AI/ML:** gradient descent, backpropagation, epoch, batch, loss function, overfitting, etc.
- **Programming:** variable, function, class, array, framework, API, repository, etc.
- **Mathematics:** derivative, matrix, vector, probability, distribution, etc.
- **General Tech:** cloud, server, database, deployment, pipeline, etc.

### 5.3 User Custom Glossary
Users can add, edit, and delete custom terms. Custom terms override built-in glossary. All glossary data stored in local SQLite database.

---

## 6. Learning Enhancement Features

### 6.1 Lecture Summary
After translating a full transcript, Qwen3-8B generates a structured Vietnamese summary:
- Key concepts, definitions, formulas
- Code examples preserved in English
- Output: Markdown file saved alongside video

### 6.2 Auto Flashcard Generator
Qwen3-8B extracts Q&A pairs from translated transcript:
- Technical definitions → "What is X?" cards
- Process explanations → "How does X work?" cards
- Export to Anki format (.apkg)

### 6.3 Code Block Detection
When transcript contains code (detected by patterns like function names, brackets, indentation keywords), the translation engine preserves the code block in English and only translates surrounding explanation.

### 6.4 Transcript History & Search
All processed videos indexed in SQLite:
- Full-text search across all translated transcripts
- Search by platform, date, topic, glossary terms
- Click search result → jump to timestamp in video

### 6.5 PDF Lecture Notes (v1.1)

Extracts key frames from video at scene changes + maps SRT text to each frame → generates a PDF study document.

**Two-layer process:**
1. **Scene Detection (auto):** FFmpeg scene filter detects significant visual changes (slide transitions, new code, new diagrams). Captures ~80-90% of important points.
2. **User Review (manual):** After auto-detection, user can add/remove frames before PDF export.

**Technical details:**

| Step | Tool | Notes |
|------|------|-------|
| Scene Detection | FFmpeg scene filter | `ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',showinfo" -vsync vfr frames/frame_%04d.png` |
| Frame Extraction | FFmpeg `-ss <time> -frames:v 1` | Export PNG, resize for PDF |
| SRT Mapping | Python timestamp matching | Each frame gets SRT lines from its timestamp to next frame |
| PDF Generation | fpdf2 | Unicode Vietnamese support, A4 layout |

**SRT-to-Frame mapping logic:**
- Frame at time T contains all SRT lines with `start_time` in range `[T, T_next)`
- If bilingual SRT: show both EN + VI (EN first, VI below)
- If English only: show English

**PDF page layout:**

| Component | Position | Detail |
|-----------|----------|--------|
| Lecture title | Header | Shown on every page |
| Frame image | Upper ~60% | Maintains aspect ratio |
| Timestamp | Below image | Format: `[HH:MM:SS]` |
| English text | Lower section | Smaller font, gray |
| Vietnamese text | Lower section | Main font, black, bold |
| Page number | Footer | Page X / Total Y |

**Module structure:**
- `src/scene_detector.py` — Scene detection + frame extraction via FFmpeg
- `src/srt_frame_mapper.py` — Map SRT lines to frames by timestamp
- `src/pdf_generator.py` — Generate PDF with fpdf2

**Performance (30-min video):** ~1-2 minutes total, ~0.5GB peak RAM. No AI models needed.

---

## 7. Output Formats

| Output | Format | Description |
|--------|--------|-------------|
| Dubbed video | .mp4 | Original video + Vietnamese audio track (original at 15-20% volume) + embedded SRT |
| Bilingual subtitle | .srt | Each entry shows English + Vietnamese |
| Vietnamese subtitle | .srt | Vietnamese only, for clean viewing |
| Vietnamese audio | .mp3 | Standalone audio track for podcast-style listening |
| Lecture summary | .md | Structured notes in Vietnamese |
| Flashcards | .apkg / .csv | Anki-compatible or CSV |
| Transcript | .txt / .md | Full bilingual transcript with timestamps |
| PDF Lecture Notes | .pdf | Frame images + bilingual SRT text + timestamps |

### 7.1 Video Playback Options

**Option A — Full export:** FFmpeg merges Vietnamese audio as second track into .mp4. File contains 2 audio tracks (original + Vietnamese). VLC, IINA, mpv can switch between them.

**Option B — Lightweight:** Export Vietnamese audio as separate .mp3. User loads manually in VLC via Audio → Add Audio Track while playing original video.

---

## 8. GUI Design (PyQt6)

### 8.1 Main Navigation

Left sidebar with platform tabs:
- **YouTube** — URL input, playlist support, batch queue
- **DeepLearning.AI** — File import (drag & drop video + subtitle)
- **Udemy** — yt-dlp download or BlackHole capture fallback
- **History** — All processed videos, search, bookmarks
- **Glossary** — Manage term packs and custom entries
- **Settings** — Model selection, TTS voice, speed limits, output preferences

### 8.2 Processing View

When a job is running:
- Progress bar with current step indicator (Downloading → STT → Translating → TTS → Merging)
- Live preview of translated subtitles as generated
- Estimated time remaining
- Queue panel showing pending jobs

### 8.3 Review View

After processing completes:
- Bilingual transcript viewer (English + Vietnamese side by side)
- Inline editing — click any translated line to correct before TTS
- Audio preview — click any line to hear Vietnamese TTS for that segment
- Export buttons for all output formats
- Tabs: **Summary**, **Flashcards**, **PDF Notes**

---

## 9. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| GUI Framework | PyQt6 | Native macOS desktop application |
| Video Download | yt-dlp | YouTube/Udemy video + subtitle download |
| Audio Capture | BlackHole 2ch + PyAudio | System audio recording (Udemy fallback) |
| Speech-to-Text | whisper.cpp (Python binding) | Audio transcription with timestamps |
| Translation | Qwen3-8B via Ollama API | EN→VI translation with glossary |
| Text-to-Speech | Piper TTS (ONNX/VITS) | Vietnamese audio generation |
| Time-Stretch | FFmpeg / librosa | Audio speed adjustment to match SRT slots |
| Video Processing | FFmpeg | Audio merge, subtitle embed, format conversion |
| Subtitle Parsing | pysrt / webvtt-py | SRT and VTT file handling |
| Database | SQLite | Transcript history, glossary, bookmarks, flashcards |
| Flashcard Export | genanki | Anki .apkg file generation |
| PDF Generation | fpdf2 | PDF Lecture Notes with Unicode Vietnamese |
| Image Processing | Pillow | Frame resize for PDF |

---

## 10. Development Phases

### Phase 1 — Core Pipeline (MVP)
- SRT parser (read .srt and .vtt files)
- Translation engine (Qwen3-8B via Ollama API + glossary)
- TTS engine (Piper TTS Vietnamese)
- Time-stretch synchronization logic
- Audio assembly (place clips at correct timestamps)
- FFmpeg merge (video + audio tracks)
- Basic CLI for testing the full pipeline

### Phase 2 — Platform Integration
- YouTube: yt-dlp integration with subtitle download
- DeepLearning.AI: file import with VTT→SRT conversion
- Udemy: yt-dlp + cookies, BlackHole fallback
- Whisper STT integration for videos without subtitles

### Phase 3 — GUI Application
- PyQt6 main window with platform tabs
- Processing view with progress tracking
- Review view with bilingual transcript editor
- Export functionality for all output formats
- Job queue for batch processing

### Phase 4 — Learning Features
- Glossary management UI
- Lecture summary generation
- Flashcard auto-generation + Anki export
- Transcript history with full-text search
- Code block detection and preservation
- PDF Lecture Notes (scene detection + frame extraction + PDF generation)

---

## 11. Performance Estimates

Estimated processing time for a typical 30-minute lecture on Mac Mini M4:

| Step | Time Estimate | Notes |
|------|--------------|-------|
| yt-dlp download | 1-2 min | Depends on internet speed |
| Whisper STT (if needed) | 3-5 min | large-v3-turbo, ~10x realtime |
| Qwen3-8B translation (~300 lines) | 10-20 min | ~15-20 tokens/sec |
| Piper TTS (~300 clips) | 2-3 min | Faster than realtime per clip |
| Time-stretch + assembly | 1-2 min | FFmpeg processing |
| Video merge | 1-2 min | Stream copy, no re-encoding |
| PDF Lecture Notes | 1-2 min | FFmpeg scene detect + fpdf2 |
| **Total (with SRT)** | **~15-27 min** | Skip Whisper step |
| **Total (without SRT)** | **~18-32 min** | Full pipeline |

Batch processing: queue multiple videos overnight. 10-video playlist (~5 hours) ≈ 5-10 hours.

---

## 12. Storage Considerations

| Item | Size Estimate |
|------|--------------|
| Ollama Qwen3-8B model | ~5GB (one-time) |
| Whisper large-v3-turbo model | ~1.5GB (one-time) |
| Piper TTS Vietnamese model | ~50MB (one-time) |
| Per 30-min video (source + outputs) | ~500MB-1GB |
| PDF Lecture Notes per video | ~5-15MB |
| SQLite database | ~50MB for hundreds of videos |

**Recommendation:** Keep source videos on external storage after processing. Only transcripts and SRT files need to remain on internal SSD for search functionality.
