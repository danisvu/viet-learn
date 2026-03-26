"""Tests for src.srt_frame_mapper — subtitle-to-frame assignment."""
from __future__ import annotations

import pytest

from src.models import BilingualEntry, FrameInfo, PageContent, SubtitleEntry
from src.srt_frame_mapper import SRTFrameMapper, _entry_start


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _frame(index: int, timestamp: float, path: str = "") -> FrameInfo:
    return FrameInfo(frame_index=index, timestamp=timestamp, frame_path=path or f"frame{index:04d}.jpg")


def _sub(idx: int, start: float, text: str = "hello") -> SubtitleEntry:
    return SubtitleEntry(index=idx, start_time=start, end_time=start + 2.0, text=text)


def _bi(idx: int, start_sec: float, en: str = "hello", vi: str = "xin chào") -> BilingualEntry:
    h, rem = divmod(int(start_sec), 3600)
    m, s = divmod(rem, 60)
    ms = int((start_sec - int(start_sec)) * 1000)
    ts = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return BilingualEntry(index=idx, start=ts, end=ts, text_en=en, text_vi=vi)


# ---------------------------------------------------------------------------
# _entry_start helper
# ---------------------------------------------------------------------------

def test_entry_start_subtitle_entry():
    e = _sub(0, 12.5)
    assert _entry_start(e) == pytest.approx(12.5)


def test_entry_start_bilingual_entry():
    e = _bi(0, 65.5)  # 1 min 5.5 sec
    assert _entry_start(e) == pytest.approx(65.5)


def test_entry_start_bilingual_entry_with_ms():
    e = _bi(0, 3723.0)  # 1h 2m 3s
    assert _entry_start(e) == pytest.approx(3723.0)


# ---------------------------------------------------------------------------
# map() — basic cases
# ---------------------------------------------------------------------------

def test_map_empty_frames_returns_empty():
    mapper = SRTFrameMapper()
    result = mapper.map([], [_sub(0, 0.0)])
    assert result == []


def test_map_no_entries_returns_empty_pages():
    frames = [_frame(1, 0.0), _frame(2, 10.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, [])
    assert len(pages) == 2
    assert all(p.entries == [] for p in pages)


def test_map_single_frame_single_entry():
    frames = [_frame(1, 0.0)]
    entries = [_sub(0, 5.0, "Neural networks")]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    assert len(pages) == 1
    assert pages[0].entries == entries


def test_map_all_entries_before_first_frame():
    frames = [_frame(1, 10.0), _frame(2, 20.0)]
    entries = [_sub(0, 0.0), _sub(1, 5.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    # Entries before first frame → assigned to first frame
    assert len(pages[0].entries) == 2
    assert len(pages[1].entries) == 0


def test_map_entries_assigned_to_correct_frames():
    frames = [_frame(1, 0.0), _frame(2, 10.0), _frame(3, 20.0)]
    entries = [
        _sub(0, 2.0),   # → frame 1
        _sub(1, 8.0),   # → frame 1 (before frame 2 at 10s)
        _sub(2, 12.0),  # → frame 2
        _sub(3, 22.0),  # → frame 3
    ]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)

    assert len(pages[0].entries) == 2   # entries 0, 1
    assert len(pages[1].entries) == 1   # entry 2
    assert len(pages[2].entries) == 1   # entry 3


def test_map_entry_exactly_at_frame_timestamp_goes_to_that_frame():
    frames = [_frame(1, 0.0), _frame(2, 10.0)]
    entry = _sub(0, 10.0)  # exactly at frame 2
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, [entry])
    assert entry in pages[1].entries
    assert pages[0].entries == []


# ---------------------------------------------------------------------------
# map() — BilingualEntry support
# ---------------------------------------------------------------------------

def test_map_bilingual_entries():
    frames = [_frame(1, 0.0), _frame(2, 30.0)]
    entries = [_bi(0, 5.0), _bi(1, 35.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    assert len(pages[0].entries) == 1
    assert len(pages[1].entries) == 1


def test_map_mixed_entry_types():
    frames = [_frame(1, 0.0)]
    entries = [_sub(0, 1.0), _bi(1, 2.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    assert len(pages[0].entries) == 2


# ---------------------------------------------------------------------------
# map() — page numbers and frame preservation
# ---------------------------------------------------------------------------

def test_map_page_numbers_are_1_based():
    frames = [_frame(1, 0.0), _frame(2, 10.0), _frame(3, 20.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, [])
    assert [p.page_number for p in pages] == [1, 2, 3]


def test_map_frame_reference_preserved():
    f1 = _frame(1, 0.0, "custom/path/frame0001.jpg")
    mapper = SRTFrameMapper()
    pages = mapper.map([f1], [])
    assert pages[0].frame is f1


def test_map_returns_page_content_instances():
    frames = [_frame(1, 0.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, [_sub(0, 1.0)])
    assert all(isinstance(p, PageContent) for p in pages)


def test_map_output_sorted_by_frame_timestamp():
    # Input frames deliberately unsorted
    frames = [_frame(2, 20.0), _frame(1, 0.0), _frame(3, 10.0)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, [])
    timestamps = [p.frame.timestamp for p in pages]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_map_large_number_of_entries(benchmark=None):
    frames = [_frame(i + 1, i * 60.0) for i in range(5)]
    entries = [_sub(j, j * 3.0) for j in range(100)]
    mapper = SRTFrameMapper()
    pages = mapper.map(frames, entries)
    total_entries = sum(len(p.entries) for p in pages)
    assert total_entries == 100
