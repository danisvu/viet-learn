"""PDF lecture notes pipeline — CLI entry point.

Chains SceneDetector → SRTFrameMapper → PDFGenerator to convert a video +
SRT file into a PDF of illustrated lecture notes.

Usage::

    python -m src.pdf_notes \\
        --video lecture.mp4 \\
        --srt   lecture.srt \\
        --output output/pdf/lecture_notes.pdf \\
        [--threshold 0.3] \\
        [--config config/config.yaml]

Steps
-----
1. Detect scene changes in the video (FFmpeg).
2. Parse the SRT subtitle file.
3. Assign each subtitle entry to its nearest scene frame.
4. Generate a PDF with one page per scene frame.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.pdf_notes",
        description="Generate illustrated PDF lecture notes from a video + SRT file.",
    )
    parser.add_argument("--video",  required=True, metavar="FILE", help="Input video file path")
    parser.add_argument("--srt",    required=True, metavar="FILE", help="Subtitle file (.srt or .vtt)")
    parser.add_argument("--output", required=True, metavar="FILE", help="Output PDF file path")
    parser.add_argument(
        "--threshold", type=float, default=None, metavar="FLOAT",
        help="Scene-change threshold (0–1). Overrides config value.",
    )
    parser.add_argument(
        "--config", default="config/config.yaml", metavar="FILE",
        help="Path to config.yaml (default: config/config.yaml)",
    )
    return parser


def run(
    video: str,
    srt: str,
    output: str,
    config_path: str = "config/config.yaml",
    threshold_override: float | None = None,
) -> Path:
    """Execute the full pipeline programmatically.

    Args:
        video: Input video path.
        srt:   Subtitle file path (.srt or .vtt).
        output: Destination PDF path.
        config_path: Path to config.yaml.
        threshold_override: If given, overrides ``scene.threshold`` from config.

    Returns:
        The :class:`pathlib.Path` of the written PDF.
    """
    # Imports are local to avoid top-level import of heavy modules in tests
    from src.config_loader import Config, load_config
    from src.pdf_generator import PDFGenerator
    from src.scene_detector import SceneDetector
    from src.srt_frame_mapper import SRTFrameMapper
    from src.srt_parser import parse_subtitle

    # ── Load configuration ─────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = load_config(config_path)

    if threshold_override is not None:
        # Patch the config in-memory without writing the file
        if hasattr(cfg, "scene") and isinstance(cfg.scene, Config):
            cfg.scene.threshold = threshold_override
        logger.info("Using threshold override: %.2f", threshold_override)

    # ── Step 1: Scene detection ────────────────────────────────────────────
    logger.info("Step 1/3 — Detecting scene changes in '%s'", video)
    detector = SceneDetector(cfg)
    frames = detector.detect(video)
    logger.info("  → %d scene frame(s) detected", len(frames))

    if not frames:
        logger.warning("No scene frames detected — PDF will be empty")

    # ── Step 2: Parse subtitles ────────────────────────────────────────────
    logger.info("Step 2/3 — Parsing subtitle file '%s'", srt)
    entries = parse_subtitle(srt)
    logger.info("  → %d subtitle entries parsed", len(entries))

    # ── Step 3: Map entries to frames ─────────────────────────────────────
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    logger.info("  → %d page(s) assembled", len(pages))

    # ── Step 4: Generate PDF ───────────────────────────────────────────────
    logger.info("Step 3/3 — Generating PDF → '%s'", output)
    gen = PDFGenerator(cfg)
    result = gen.generate(pages, output)
    logger.info("Done. PDF saved: %s", result)
    return result


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    video_path = Path(args.video)
    srt_path = Path(args.srt)

    if not video_path.exists():
        parser.error(f"Video file not found: {video_path}")
    if not srt_path.exists():
        parser.error(f"Subtitle file not found: {srt_path}")

    try:
        run(
            video=str(video_path),
            srt=str(srt_path),
            output=args.output,
            config_path=args.config,
            threshold_override=args.threshold,
        )
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
