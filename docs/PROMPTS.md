# VietLearn — Prompts cho Claude Code

> **Cách dùng:** Copy-paste từng prompt vào Claude Code. Mỗi prompt = 1 đầu việc.
> **Phương pháp:** TDD — viết test trước, code sau.
> **Thứ tự:** Làm từ trên xuống dưới trong mỗi Phase.

---

## Phase 1 — Core Pipeline (MVP)

### Prompt 1.0 — Config Loader

Tạo module `src/config_loader.py`: đọc file `config/config.yaml` bằng PyYAML, trả về object config dùng chung cho toàn bộ dự án. Phải hỗ trợ: truy cập config theo key path (ví dụ `config.ollama.base_url`), giá trị mặc định khi key không tồn tại, và validation các giá trị bắt buộc. Viết test `tests/test_config_loader.py` trước — test đọc file yaml hợp lệ, file không tồn tại, key thiếu.

---

### Prompt 1.1 — SRT Parser

Tạo module `src/srt_parser.py`: đọc file .srt và .vtt, trả về `list[SubtitleEntry]` trong đó mỗi entry chứa `index`, `start_time` (seconds float), `end_time` (seconds float), và `text` (string). Dùng thư viện `pysrt` cho .srt và `webvtt-py` cho .vtt. VTT phải được tự động chuyển sang cùng format output với SRT. Viết test `tests/test_srt_parser.py` trước — test với file .srt hợp lệ, file .vtt, file rỗng, file bị lỗi format. Tạo file test data trong `data/` nếu cần.

---

### Prompt 1.2 — Translator (Ollama API)

Tạo module `src/translator.py`: nhận `list[SubtitleEntry]` (tiếng Anh), gọi Ollama API (`POST http://localhost:11434/api/generate`) với model `qwen3:8b` để dịch từng entry sang tiếng Việt. Prompt cho model phải yêu cầu: chỉ output bản dịch, không thêm giải thích. Trước khi dịch, kiểm tra glossary — nếu text chứa glossary term, thay thế/giữ nguyên/annotate theo mode của term đó (đọc `docs/DESIGN.md` section 5 về Glossary Modes). Module phải hỗ trợ: retry khi API timeout, progress callback cho mỗi entry đã dịch, batch mode (không gọi API quá nhanh). Trả về `list[SubtitleEntry]` mới với text đã dịch sang tiếng Việt. Đọc config từ `config.yaml` cho Ollama URL, model name, timeout. Viết test `tests/test_translator.py` trước — mock Ollama API response, test glossary replacement, test retry logic, test với danh sách rỗng.

---

### Prompt 1.3 — SRT Writer

Tạo module `src/srt_writer.py`: nhận `list[SubtitleEntry]` tiếng Anh và `list[SubtitleEntry]` tiếng Việt (cùng timestamps), tạo 2 file .srt output: (1) bilingual — mỗi entry hiển thị dòng EN trước, dòng VI sau, (2) Vietnamese only — chỉ text tiếng Việt. Giữ nguyên timestamps gốc. Format SRT chuẩn: index, timecode `HH:MM:SS,mmm --> HH:MM:SS,mmm`, text, dòng trống. Viết test `tests/test_srt_writer.py` trước — test output bilingual, output VI-only, kiểm tra format timestamp đúng chuẩn SRT, test với entries chứa ký tự Unicode tiếng Việt (dấu).

---

### Prompt 1.4 — TTS Engine (Piper)

Tạo module `src/tts_engine.py`: nhận một `SubtitleEntry` (tiếng Việt), gọi Piper TTS command line (`piper --model vi_VN-vais1000-medium --output_file <path>`) để tạo file .wav cho entry đó. Module phải hỗ trợ: tạo audio cho danh sách entries (lặp qua từng cái), lưu mỗi clip vào thư mục tạm với tên file theo index, đo duration thực tế của mỗi clip bằng `soundfile` hoặc `librosa`, trả về `list[AudioClip]` chứa `file_path`, `actual_duration`, `target_duration` (từ SRT slot). Đọc TTS model name từ `config.yaml`. Viết test `tests/test_tts_engine.py` trước — test tạo 1 clip từ text tiếng Việt ngắn, kiểm tra file .wav tồn tại và duration > 0. Lưu ý: test cần Piper TTS đã cài (skip test nếu piper không có, dùng `pytest.mark.skipif`).

---

### Prompt 1.5 — Time Stretcher

Tạo module `src/time_stretcher.py`: nhận một `AudioClip` (chứa file_path, actual_duration, target_duration), tính speed ratio = actual/target. Logic xử lý: (1) nếu ratio trong khoảng 0.75–1.6: dùng `librosa.effects.time_stretch` hoặc FFmpeg `atempo` filter để stretch/compress audio đúng target_duration, (2) nếu ratio > 1.6: trả về warning kèm option (accept fast, hoặc cần summarize text — module không tự summarize, chỉ báo), (3) nếu ratio < 0.75: giữ nguyên audio, pad silence ở cuối cho đủ target_duration. Output: file .wav mới với duration khớp chính xác target. Đọc speed limits từ `config.yaml`. Viết test `tests/test_time_stretcher.py` trước — test case ratio bình thường (1.2x), ratio quá nhanh (2.0x → warning), ratio quá chậm (0.5x → pad silence), kiểm tra output duration.

---

### Prompt 1.6 — Audio Merger + FFmpeg

Tạo module `src/audio_merger.py`: nhận `list[AudioClip]` (đã time-stretch, mỗi clip có start_time và file_path) + video file path. (1) Ghép tất cả audio clips vào một audio track duy nhất — mỗi clip được đặt tại đúng start_time, khoảng trống giữa các clip là silence. Tổng duration = duration video gốc. Dùng `pydub` hoặc raw numpy + soundfile. (2) Gọi FFmpeg merge video: `ffmpeg -i video.mp4 -i vi_audio.wav -filter_complex "[1:a]volume=1.0[vi];[0:a]volume=0.15[en]" -map 0:v -map "[en]" -map "[vi]" -c:v copy output.mp4`. Đọc original audio volume từ `config.yaml`. Tạo thêm option export mp3 riêng (audio tiếng Việt). Viết test `tests/test_audio_merger.py` trước — test assembly logic (clips đặt đúng vị trí), test FFmpeg command generation (mock subprocess). Test end-to-end cần video mẫu trong `data/`.

---

### Prompt 1.7 — Pipeline Orchestrator

Tạo module `src/pipeline.py`: ghép tất cả module thành pipeline hoàn chỉnh. Input: video file + SRT file (hoặc VTT). Output: tất cả file trong bảng Output (docs/DESIGN.md section 7). Pipeline flow: parse SRT → translate → write SRT files → TTS cho từng entry → time-stretch từng clip → merge audio → FFmpeg merge video. Module phải: log rõ ràng từng bước (`logging`), báo progress callback (step name + percentage), xử lý error gracefully (nếu TTS 1 entry fail → skip entry đó, log warning, tiếp tục), lưu tất cả output vào thư mục chỉ định. Viết test `tests/test_pipeline.py` — test flow với mock modules, test error handling khi một bước fail.

---

### Prompt 1.8 — CLI Entry Point

Tạo file `src/__main__.py` hoặc `cli.py`: cho phép chạy pipeline từ command line:
```
python -m src --video video.mp4 --srt subtitles.srt --output ./output/ [--glossary glossary.json]
```
Parse arguments bằng `argparse`. Hiển thị progress trong terminal. Test thủ công — không cần pytest cho CLI.

---

## Phase 2 — Platform Integration

### Prompt 2.1 — YouTube Downloader
Tạo module `src/youtube_downloader.py`: nhận YouTube URL (single video hoặc playlist), dùng `yt-dlp` Python API để tải video + SRT. Hỗ trợ: chọn chất lượng video, ưu tiên creator subtitles > auto-generated, fallback flag khi không có SRT. Viết test trước.

### Prompt 2.2 — DeepLearning.AI Importer
Tạo module `src/dlai_importer.py`: nhận đường dẫn video file + VTT/SRT file do user cung cấp. Validate format, tự động convert VTT → SRT nếu cần. Copy files vào thư mục dự án. Viết test trước.

### Prompt 2.3 — Udemy Downloader
Tạo module `src/udemy_downloader.py`: yt-dlp + browser cookies. Detect DRM failure (HTTP 403) → return fallback flag. Viết test trước (mock yt-dlp).

### Prompt 2.4 — BlackHole Audio Capture
Tạo module `src/audio_capture.py`: ghi audio hệ thống qua BlackHole 2ch bằng PyAudio. Start/stop recording, save WAV. Viết test trước (mock PyAudio).

### Prompt 2.5 — Whisper STT Integration
Tạo module `src/whisper_stt.py`: nhận audio file, chạy whisper.cpp (Python binding) để tạo SRT từ audio. Output: file .srt với timestamps. Viết test trước.

---

## Phase 3 — GUI Application

### Prompt 3.1 — Main Window + Navigation
PyQt6 main window với left sidebar: YouTube, DeepLearning.AI, Udemy, History, Glossary, Settings. Mỗi tab load widget riêng.

### Prompt 3.2 — YouTube Tab
URL input, playlist detection, batch queue, download button.

### Prompt 3.3 — DeepLearning.AI Tab
Drag-and-drop area cho video + subtitle file, validate + import.

### Prompt 3.4 — Processing View
Progress bar, step indicator, live subtitle preview, ETA, queue panel.

### Prompt 3.5 — Review View
Bilingual transcript editor (side-by-side), inline edit, audio preview per line, export buttons. Tabs: Summary, Flashcards, PDF Notes.

### Prompt 3.6 — Settings View
Model selection, TTS voice, speed limits, output preferences, storage management.

---

## Phase 4 — Learning Features

### Prompt 4.1 — Glossary Management UI
CRUD glossary terms trong PyQt6. Filter by pack (AI/ML, Programming, Math, Custom). Import/export JSON.

### Prompt 4.2 — Lecture Summary Generator
Gọi Qwen3-8B với full translated transcript → structured Vietnamese summary (key concepts, definitions, code blocks). Save as .md.

### Prompt 4.3 — Flashcard Auto-Generator
Qwen3-8B scan transcript → extract Q&A pairs → export Anki .apkg via `genanki`.

### Prompt 4.4 — Transcript History & Search
SQLite full-text search across all transcripts. Search by platform, date, topic. Click result → jump to timestamp.

### Prompt 4.5a — Scene Detector Module
Tạo module `src/scene_detector.py`: nhận đường dẫn video, dùng FFmpeg scene filter (threshold từ `config.yaml`) để phát hiện điểm chuyển cảnh, trích xuất frame tại các điểm đó. Trả về `list[FrameInfo]` chứa timestamp và đường dẫn ảnh. Viết test trước.

### Prompt 4.5b — SRT-Frame Mapper Module
Tạo module `src/srt_frame_mapper.py`: nhận `list[FrameInfo]` + parsed SRT, gắn các dòng SRT vào frame gần nhất theo timestamp. Hỗ trợ cả SRT đơn ngữ và song ngữ. Trả về `list[PageContent]` chứa frame + danh sách dòng text. Viết test trước.

### Prompt 4.5c — PDF Generator Module
Tạo module `src/pdf_generator.py`: nhận `list[PageContent]`, tạo PDF với fpdf2. Mỗi trang: ảnh (60% chiều cao) + timestamp + text EN (nhỏ, xám) + text VI (bold). Dùng font hỗ trợ Unicode Vietnamese. Config từ `config.yaml`. Viết test trước.

### Prompt 4.5d — PDF Notes CLI
Ghép 3 module thành pipeline: video + SRT → scene detect → map SRT → generate PDF. CLI: `python -m src.pdf_notes --video --srt --output --threshold`. Test end-to-end với video mẫu.
