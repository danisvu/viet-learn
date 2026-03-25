from __future__ import annotations

from pathlib import Path

import pysrt
import webvtt

from src.models import SubtitleEntry


def _srt_time_to_seconds(t) -> float:
    return t.hours * 3600 + t.minutes * 60 + t.seconds + t.milliseconds / 1000.0


def parse_srt(path: str) -> list[SubtitleEntry]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SRT file not found: {path}")
    subs = pysrt.open(str(p), encoding="utf-8")
    return [
        SubtitleEntry(
            index=sub.index,
            start_time=_srt_time_to_seconds(sub.start),
            end_time=_srt_time_to_seconds(sub.end),
            text=sub.text.replace("\n", " ").strip(),
        )
        for sub in subs
    ]


def parse_vtt(path: str) -> list[SubtitleEntry]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"VTT file not found: {path}")
    entries = []
    for idx, caption in enumerate(webvtt.read(str(p)), start=1):
        def _vtt_ts(ts: str) -> float:
            parts = ts.split(":")
            if len(parts) == 3:
                h, m, s = parts
            else:
                h, m, s = 0, parts[0], parts[1]
            return int(h) * 3600 + int(m) * 60 + float(s)

        entries.append(SubtitleEntry(
            index=idx,
            start_time=_vtt_ts(caption.start),
            end_time=_vtt_ts(caption.end),
            text=caption.text.replace("\n", " ").strip(),
        ))
    return entries


def parse_subtitle(path: str) -> list[SubtitleEntry]:
    """Auto-detect format by extension and parse."""
    ext = Path(path).suffix.lower()
    if ext == ".srt":
        return parse_srt(path)
    elif ext == ".vtt":
        return parse_vtt(path)
    else:
        raise ValueError(f"Unsupported subtitle format: {ext}")
