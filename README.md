# VietLearn — Hướng Dẫn Cài Đặt & Chạy Project

## 1. Yêu Cầu Hệ Thống

| Phần mềm | Trạng thái trên máy bạn | Ghi chú |
|-----------|:-----------------------:|---------|
| **Python 3.11** | ✅ Đã có | via pyenv |
| **FFmpeg** | ✅ Đã có | `/opt/homebrew/bin/ffmpeg` |
| **Ollama** | ✅ Đã có | `/opt/homebrew/bin/ollama` |
| **yt-dlp** (Python) | ✅ Đã có | trong venv |
| **Piper TTS** | ❌ **Chưa cài** | cần cài cho Phase 1 TTS |
| **PyAudio** | ❌ **Chưa cài** | cần cho Phase 2 audio capture |
| **pywhispercpp** | ❌ **Chưa cài** | cần cho Phase 2 Whisper STT |

---

## 2. Cài Đặt Từng Bước

### 2.1 Clone & tạo virtual environment (nếu chưa có)

```bash
git clone https://github.com/danisvu/viet-learn.git
cd viet-learn
python3.11 -m venv venv
```

### 2.2 Fix venv pip (⚠️ venv hiện tại bị broken pip symlink)

```bash
# Tạo lại pip symlink bằng cách reinstall pip trong venv
venv/bin/python -m ensurepip --upgrade
venv/bin/python -m pip install --upgrade pip
```

### 2.3 Cài Python dependencies

```bash
venv/bin/python -m pip install -r requirements.txt
```

### 2.4 Cài Piper TTS (cho chức năng Text-to-Speech)

```bash
# Cài piper binary
venv/bin/python -m pip install piper-tts

# Tải model giọng Việt (vi_VN-vais1000-medium)
mkdir -p piper_models/vi/vi_VN/vais1000/medium
cd piper_models/vi/vi_VN/vais1000/medium
curl -LO "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
curl -LO "https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx.json"
cd -
```

### 2.5 Cài Ollama + Qwen3-8B model (cho dịch thuật)

```bash
# Cài Ollama (nếu chưa có)
brew install ollama

# Khởi động Ollama server
ollama serve &

# Tải model Qwen3-8B
ollama pull qwen3:8b
```

### 2.6 Cài thêm (tùy chọn — cho Phase 2)

```bash
# PyAudio — ghi audio hệ thống qua BlackHole
brew install portaudio
venv/bin/python -m pip install pyaudio

# pywhispercpp — speech-to-text
venv/bin/python -m pip install pywhispercpp
```

---

## 3. Chạy Project

### 3.1 Chạy GUI (giao diện đồ họa — khuyến nghị)

```bash
venv/bin/python -c "from src.gui.main_window import app_main; app_main()"
```

Cửa sổ VietLearn sẽ hiện ra với sidebar gồm các tab:
- **YouTube** — paste URL video/playlist, download + xử lý tự động
- **DeepLearning.AI** — kéo thả video + subtitle file
- **Udemy** — nhập URL + dùng browser cookies
- **History** — lịch sử các video đã xử lý
- **Search** — tìm kiếm full-text trong transcript
- **Glossary** — quản lý từ vựng chuyên ngành
- **Editor** — xem/chỉnh sửa transcript song ngữ
- **Settings** — cấu hình model, giọng TTS, tốc độ

### 3.2 Chạy CLI (command line)

```bash
# Cú pháp cơ bản
venv/bin/python -m src \
  --video path/to/video.mp4 \
  --srt path/to/subtitles.srt \
  --output ./output/

# Với glossary tuỳ chỉnh
venv/bin/python -m src \
  --video lecture.mp4 \
  --srt lecture.srt \
  --output ./output/ \
  --glossary glossary.json

# Với file VTT
venv/bin/python -m src \
  --video lecture.mp4 \
  --srt lecture.vtt \
  --output ./output/
```

**CLI Pipeline flow:**
1. Parse SRT/VTT → 2. Dịch EN→VI (Ollama) → 3. Ghi file SRT →
4. TTS từng entry → 5. Time-stretch → 6. Ghép audio → 7. Merge video

### 3.3 Tạo PDF Notes từ video

```bash
venv/bin/python -m src.pdf_notes \
  --video lecture.mp4 \
  --srt lecture.srt \
  --output ./output/pdf/
```

### 3.4 Chạy tests

```bash
# Toàn bộ test suite
venv/bin/python -m pytest tests/ -v

# Chạy test một module cụ thể
venv/bin/python -m pytest tests/test_srt_parser.py -v

# Chạy test với coverage (cần cài pytest-cov)
venv/bin/python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## 4. Cấu Hình

File config tại `config/config.yaml`. Các phần quan trọng:

| Section | Mô tả | Mặc định |
|---------|--------|----------|
| `ollama.model` | Model dịch thuật | `qwen3:8b` |
| `ollama.base_url` | Ollama API URL | `http://localhost:11434` |
| `tts.model` | Giọng TTS tiếng Việt | `vi_VN-vais1000-medium` |
| `audio.original_volume` | Âm lượng gốc (nền) | `0.15` |
| `time_stretch.max_speed_ratio` | Tốc độ tối đa TTS | `1.6` |
| `download.output_dir` | Thư mục tải video | `output/downloads` |

---

## 5. Cấu Trúc Output

Sau khi chạy pipeline, thư mục output chứa:

```
output/
├── video_bilingual.srt      # SRT song ngữ EN + VI
├── video_vi.srt             # SRT chỉ tiếng Việt
├── video_vi_audio.wav       # Audio tiếng Việt
├── video_output.mp4         # Video với 2 audio tracks
└── video_vi.mp3             # Audio MP3 tiếng Việt (tuỳ chọn)
```

---

## 6. Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| `connection refused :11434` | Chạy `ollama serve` trước |
| `FileNotFoundError: piper` | Xem lại bước 2.4, cài piper-tts |
| `No module named 'pyaudio'` | Xem lại bước 2.6 |
| `pip: bad interpreter` | Chạy bước 2.2 để fix pip |
| GUI không hiện | Kiểm tra PyQt6: `venv/bin/python -c "import PyQt6"` |
| Model dịch chậm | Kiểm tra GPU: `ollama ps` |

---

> **Lưu ý:** Luôn đảm bảo Ollama server đang chạy (`ollama serve`) trước khi dùng chức năng dịch.
