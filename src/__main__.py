"""
VietLearn CLI — chạy pipeline từ command line.

Ví dụ:
    python -m src --video video.mp4 --srt subtitles.srt --output ./output/
    python -m src --video video.mp4 --srt subtitles.srt --output ./output/ --glossary glossary.json
    python -m src --video video.mp4 --srt subtitles.vtt --output ./output/ --config my_config.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from src.models import GlossaryTerm, GlossaryMode
from src.pipeline import Pipeline, PipelineConfig, PipelineStep, load_pipeline_from_config


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vietlearn")


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

STEP_LABELS = {
    PipelineStep.PARSING: "Đọc subtitle",
    PipelineStep.TRANSLATING: "Dịch",
    PipelineStep.WRITING_SRT: "Ghi SRT",
    PipelineStep.TTS: "Text-to-Speech",
    PipelineStep.STRETCHING: "Time-stretch",
    PipelineStep.ASSEMBLING: "Ghép audio",
    PipelineStep.MERGING: "Merge video",
    PipelineStep.DONE: "Hoàn tất",
}

_current_step: str = ""


def _progress(step: PipelineStep, pct: float, msg: str = "") -> None:
    global _current_step
    label = STEP_LABELS.get(step, step.value)
    bar_len = 30
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    suffix = f"  {msg}" if msg else ""
    line = f"\r[{bar}] {pct * 100:5.1f}%  {label}{suffix}"
    print(line, end="", flush=True)
    if pct >= 1.0:
        print()  # newline after step completes


# ---------------------------------------------------------------------------
# Glossary loader
# ---------------------------------------------------------------------------

def _load_glossary(path: str) -> list[GlossaryTerm]:
    """Load glossary from JSON file.

    Expected format:
    [
        {"english": "epoch", "vietnamese": "vòng huấn luyện", "mode": "replace"},
        {"english": "gradient descent", "vietnamese": "", "mode": "keep_english"},
        {"english": "overfitting", "vietnamese": "học quá khớp", "mode": "translate_annotate"}
    ]
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    terms = []
    for item in data:
        terms.append(GlossaryTerm(
            english=item["english"],
            vietnamese=item.get("vietnamese", ""),
            mode=GlossaryMode(item["mode"]),
        ))
    return terms


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description="VietLearn — dịch video giáo dục sang tiếng Việt",
    )
    parser.add_argument("--video", required=True, metavar="FILE",
                        help="Đường dẫn tới file video (.mp4, .mkv, ...)")
    parser.add_argument("--srt", required=True, metavar="FILE",
                        help="Đường dẫn tới file subtitle (.srt hoặc .vtt)")
    parser.add_argument("--output", required=True, metavar="DIR",
                        help="Thư mục lưu tất cả output")
    parser.add_argument("--glossary", metavar="FILE", default=None,
                        help="File glossary JSON (tùy chọn)")
    parser.add_argument("--config", metavar="FILE", default="config/config.yaml",
                        help="File config YAML (mặc định: config/config.yaml)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Mức log (mặc định: INFO)")
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Validate inputs
    video_path = Path(args.video)
    srt_path = Path(args.srt)
    if not video_path.exists():
        print(f"Lỗi: không tìm thấy file video: {args.video}", file=sys.stderr)
        return 1
    if not srt_path.exists():
        print(f"Lỗi: không tìm thấy file subtitle: {args.srt}", file=sys.stderr)
        return 1

    print(f"VietLearn Pipeline")
    print(f"  Video   : {args.video}")
    print(f"  Subtitle: {args.srt}")
    print(f"  Output  : {args.output}")
    if args.glossary:
        print(f"  Glossary: {args.glossary}")
    print()

    # Load pipeline
    pipeline = load_pipeline_from_config(
        output_dir=args.output,
        config_path=args.config,
    )

    # Inject glossary if provided
    if args.glossary:
        try:
            glossary = _load_glossary(args.glossary)
            pipeline.config.translator.glossary = glossary  # type: ignore[attr-defined]
            print(f"Đã tải {len(glossary)} từ trong glossary.\n")
        except Exception as exc:
            print(f"Cảnh báo: không tải được glossary: {exc}", file=sys.stderr)

    start = time.monotonic()
    try:
        result = pipeline.run(
            video_path=str(video_path),
            subtitle_path=str(srt_path),
            progress_callback=_progress,
        )
    except Exception as exc:
        print(f"\nLỗi pipeline: {exc}", file=sys.stderr)
        logger.exception("Pipeline failed")
        return 1

    elapsed = time.monotonic() - start
    minutes, seconds = divmod(int(elapsed), 60)

    print(f"\nHoàn tất trong {minutes:02d}:{seconds:02d}")
    print(f"\nOutput files:")
    for key, path in result.items():
        if path:
            print(f"  {key:15s}: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
