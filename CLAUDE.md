# VietLearn — CLAUDE.md

> **Claude Code tự động đọc file này khi khởi động.**
> Đây là "bộ nhớ" của dự án — chứa quy trình, quy ước, và bản đồ code.

---

## Dự án là gì?

VietLearn là ứng dụng macOS desktop (Python + PyQt6) dịch video bài giảng tiếng Anh sang tiếng Việt. Chạy 100% local trên Mac Mini M4 (24GB RAM, 256GB SSD). Xử lý video từ YouTube, DeepLearning.AI, Udemy — tạo ra video lồng tiếng VI, phụ đề song ngữ, audio MP3, tóm tắt, và flashcard.

---

## Phase hiện tại: Phase 1 — Core Pipeline (MVP)

### Mục tiêu Phase 1
Xây dựng pipeline xử lý hoàn chỉnh từ SRT → video lồng tiếng, chạy qua CLI.

### 6 module cần code (theo thứ tự)
1. `src/srt_parser.py` — Đọc file .srt và .vtt, trả về list subtitle entries
2. `src/translator.py` — Dịch EN→VI qua Ollama API (Qwen3-8B) + glossary
3. `src/srt_writer.py` — Tạo file .srt song ngữ và .srt tiếng Việt
4. `src/tts_engine.py` — Piper TTS tạo audio tiếng Việt cho từng entry
5. `src/time_stretcher.py` — Time-stretch audio khớp SRT timestamp (0.75x–1.6x)
6. `src/audio_merger.py` — Ghép clips + FFmpeg merge vào video

### Module phụ trợ
- `src/config_loader.py` — Đọc config từ `config/config.yaml`
- `src/glossary.py` — Quản lý glossary terms (SQLite)
- `src/pipeline.py` — Orchestrator ghép tất cả module thành pipeline

---

## Cấu trúc thư mục

```
viet-learn/
├── CLAUDE.md                  ← File này (tự động đọc)
├── config/
│   └── config.yaml            ← Cấu hình tập trung (đọc khi cần giá trị)
├── docs/
│   ├── DESIGN.md              ← Thiết kế kỹ thuật chi tiết (đọc khi cần hiểu logic)
│   └── PROMPTS.md             ← Danh sách prompt phân rã (người dùng copy-paste)
├── src/                       ← Code chính
│   ├── __init__.py
│   ├── config_loader.py
│   ├── srt_parser.py
│   ├── translator.py
│   ├── srt_writer.py
│   ├── tts_engine.py
│   ├── time_stretcher.py
│   ├── audio_merger.py
│   ├── glossary.py
│   └── pipeline.py
├── tests/                     ← Test files (1 test file per module)
│   ├── __init__.py
│   ├── test_srt_parser.py
│   ├── test_translator.py
│   ├── test_srt_writer.py
│   ├── test_tts_engine.py
│   ├── test_time_stretcher.py
│   ├── test_audio_merger.py
│   └── test_glossary.py
├── data/                      ← File mẫu để test
├── output/                    ← Kết quả xuất ra
├── requirements.txt
├── .gitignore
└── venv/                      ← Virtual environment (Git bỏ qua)
```

---

## Phương pháp: TDD (Test-Driven Development)

**Quy trình bắt buộc cho mỗi module:**
1. Viết test trước — mô tả module phải làm được gì
2. Chạy test → FAIL (chưa có code)
3. Viết code cho đến khi test PASS
4. Refactor nếu cần, đảm bảo test vẫn pass

**Chạy test:** `pytest tests/ -v`

---

## Rules

### ĐƯỢC LÀM
- Tạo/sửa file trong `src/` và `tests/`
- Chạy pytest, chạy lệnh FFmpeg
- Cài thư viện đã có trong `requirements.txt`
- Đọc file trong `data/` để test
- Tạo file mới trong `output/`
- Đọc `docs/DESIGN.md` khi cần hiểu thiết kế
- Đọc `config/config.yaml` khi cần giá trị cấu hình

### KHÔNG ĐƯỢC LÀM
- ❌ Không đổi tech stack (ví dụ đổi Piper TTS sang model khác) mà chưa hỏi
- ❌ Không hardcode đường dẫn, port, tham số → luôn đọc từ `config.yaml`
- ❌ Không viết file > 300 dòng → tách nhỏ
- ❌ Không xoá file đã commit mà chưa hỏi
- ❌ Không cài thư viện mới ngoài `requirements.txt` mà chưa hỏi
- ❌ Không sửa `CLAUDE.md` hoặc `docs/DESIGN.md`
- ❌ Không bỏ qua test → mỗi module phải có test
- ❌ Không tự sửa lỗi kiến trúc lớn mà chưa báo → giải thích lỗi + đề xuất hướng sửa trước

### QUY ƯỚC CODE
- Python PEP 8, type hints cho mọi function
- Docstring cho mỗi class và public method
- Comment code bằng tiếng Anh
- Tên biến, hàm, class bằng tiếng Anh
- Log rõ ràng ở mỗi bước pipeline bằng module `logging`
- Xử lý error gracefully — không crash khi một bước thất bại
- Git commit message bằng tiếng Anh: `type: mô tả ngắn`
  - Ví dụ: `feat: add SRT parser module`, `fix: handle empty SRT file`, `test: add translator unit tests`

---

## Thông số quan trọng (đọc chi tiết trong config.yaml)

| Thông số | Giá trị |
|----------|---------|
| Ollama API | `http://localhost:11434` |
| Model dịch | `qwen3:8b` |
| TTS voice | `vi_VN-vais1000-medium` |
| Time-stretch min | 0.75x |
| Time-stretch max | 1.6x |
| Original audio volume | 15–20% |
| RAM budget peak | ~12GB (trong 18GB khả dụng) |

---

## Khi cần thêm thông tin

- **Logic module chi tiết** → đọc `docs/DESIGN.md`
- **Prompt để giao việc** → đọc `docs/PROMPTS.md`
- **Giá trị config** → đọc `config/config.yaml`
- **Thư viện Python** → đọc `requirements.txt`
