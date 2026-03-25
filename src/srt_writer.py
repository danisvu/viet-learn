from __future__ import annotations

from pathlib import Path

from src.models import SubtitleEntry


def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timecode: HH:MM:SS,mmm"""
    total_ms = int(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _timecode_line(entry: SubtitleEntry) -> str:
    return f"{format_timestamp(entry.start_time)} --> {format_timestamp(entry.end_time)}"


def _render_blocks(blocks: list[str]) -> str:
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


def write_bilingual_srt(
    en_entries: list[SubtitleEntry],
    vi_entries: list[SubtitleEntry],
    output_path: str,
) -> None:
    """Write a bilingual SRT file: EN line first, VI line second per entry."""
    if len(en_entries) != len(vi_entries):
        raise ValueError(
            f"en_entries and vi_entries must be same length, "
            f"got {len(en_entries)} and {len(vi_entries)}"
        )

    blocks = []
    for en, vi in zip(en_entries, vi_entries):
        blocks.append(f"{en.index}\n{_timecode_line(en)}\n{en.text}\n{vi.text}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_blocks(blocks), encoding="utf-8")


def write_vietnamese_srt(
    en_entries: list[SubtitleEntry],
    vi_entries: list[SubtitleEntry],
    output_path: str,
) -> None:
    """Write a Vietnamese-only SRT file using timestamps from en_entries."""
    if len(en_entries) != len(vi_entries):
        raise ValueError(
            f"en_entries and vi_entries must be same length, "
            f"got {len(en_entries)} and {len(vi_entries)}"
        )

    blocks = []
    for en, vi in zip(en_entries, vi_entries):
        blocks.append(f"{en.index}\n{_timecode_line(en)}\n{vi.text}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_blocks(blocks), encoding="utf-8")
