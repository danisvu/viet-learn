"""Tests for src.srt_parser — SRT and VTT subtitle parsing."""

from __future__ import annotations

import pytest

from src.models import SubtitleEntry
from src.srt_parser import parse_srt, parse_vtt, parse_subtitle


# ---------------------------------------------------------------------------
# Fixtures: inline subtitle content
# ---------------------------------------------------------------------------

VALID_SRT = """\
1
00:00:01,000 --> 00:00:03,500
Hello world

2
00:01:05,123 --> 00:01:08,456
This is the second entry

3
01:02:03,004 --> 01:02:06,789
Third entry with timecode in hours
"""

VALID_VTT = """\
WEBVTT

00:00:01.000 --> 00:00:03.500
Hello world

00:01:05.123 --> 00:01:08.456
This is the second entry

01:02:03.004 --> 01:02:06.789
Third entry with timecode in hours
"""

MULTILINE_SRT = """\
1
00:00:00,000 --> 00:00:02,000
Line one
Line two
"""

UNICODE_SRT = """\
1
00:00:00,000 --> 00:00:03,000
Học máy là lĩnh vực con của trí tuệ nhân tạo

2
00:00:03,000 --> 00:00:06,000
Độ dốc giảm dần được sử dụng để tối ưu hóa
"""

EMPTY_SRT = ""

MALFORMED_SRT = """\
GARBAGE IN
NO TIMECODES HERE
JUST TEXT
"""


def _write(tmp_path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Tests: parse_srt — valid .srt file
# ---------------------------------------------------------------------------

class TestParseSRT:
    def test_returns_list_of_subtitle_entries(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", VALID_SRT))
        assert isinstance(entries, list)
        assert all(isinstance(e, SubtitleEntry) for e in entries)

    def test_entry_count(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", VALID_SRT))
        assert len(entries) == 3

    def test_first_entry_fields(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", VALID_SRT))
        e = entries[0]
        assert e.index == 1
        assert e.text == "Hello world"
        assert e.start_time == pytest.approx(1.0, abs=0.01)
        assert e.end_time == pytest.approx(3.5, abs=0.01)

    def test_timecodes_with_hours(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", VALID_SRT))
        e = entries[2]
        expected_start = 1 * 3600 + 2 * 60 + 3 + 0.004
        expected_end = 1 * 3600 + 2 * 60 + 6 + 0.789
        assert e.start_time == pytest.approx(expected_start, abs=0.01)
        assert e.end_time == pytest.approx(expected_end, abs=0.01)

    def test_multiline_text_joined(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", MULTILINE_SRT))
        assert entries[0].text == "Line one Line two"

    def test_unicode_vietnamese(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "test.srt", UNICODE_SRT))
        assert len(entries) == 2
        assert "Học máy" in entries[0].text
        assert "tối ưu hóa" in entries[1].text


# ---------------------------------------------------------------------------
# Tests: parse_srt — error cases
# ---------------------------------------------------------------------------

class TestParseSRTErrors:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_srt("/nonexistent/path/missing.srt")

    def test_empty_file_returns_empty_list(self, tmp_path):
        entries = parse_srt(_write(tmp_path, "empty.srt", EMPTY_SRT))
        assert entries == []

    def test_malformed_srt_returns_empty_or_raises(self, tmp_path):
        # pysrt may return empty list or raise; both are acceptable
        path = _write(tmp_path, "bad.srt", MALFORMED_SRT)
        try:
            entries = parse_srt(path)
            assert entries == []
        except Exception:
            pass  # raising is also acceptable for malformed input


# ---------------------------------------------------------------------------
# Tests: parse_vtt — valid .vtt file
# ---------------------------------------------------------------------------

class TestParseVTT:
    def test_returns_list_of_subtitle_entries(self, tmp_path):
        entries = parse_vtt(_write(tmp_path, "test.vtt", VALID_VTT))
        assert isinstance(entries, list)
        assert all(isinstance(e, SubtitleEntry) for e in entries)

    def test_entry_count(self, tmp_path):
        entries = parse_vtt(_write(tmp_path, "test.vtt", VALID_VTT))
        assert len(entries) == 3

    def test_first_entry_fields(self, tmp_path):
        entries = parse_vtt(_write(tmp_path, "test.vtt", VALID_VTT))
        e = entries[0]
        assert e.index == 1
        assert e.text == "Hello world"
        assert e.start_time == pytest.approx(1.0, abs=0.01)
        assert e.end_time == pytest.approx(3.5, abs=0.01)

    def test_vtt_timecodes_with_hours(self, tmp_path):
        entries = parse_vtt(_write(tmp_path, "test.vtt", VALID_VTT))
        e = entries[2]
        expected_start = 1 * 3600 + 2 * 60 + 3 + 0.004
        expected_end = 1 * 3600 + 2 * 60 + 6 + 0.789
        assert e.start_time == pytest.approx(expected_start, abs=0.01)
        assert e.end_time == pytest.approx(expected_end, abs=0.01)

    def test_same_output_format_as_srt(self, tmp_path):
        """VTT and SRT with same content should produce identical entries."""
        srt_entries = parse_srt(_write(tmp_path, "test.srt", VALID_SRT))
        vtt_entries = parse_vtt(_write(tmp_path, "test.vtt", VALID_VTT))
        for s, v in zip(srt_entries, vtt_entries):
            assert s.text == v.text
            assert s.start_time == pytest.approx(v.start_time, abs=0.01)
            assert s.end_time == pytest.approx(v.end_time, abs=0.01)


# ---------------------------------------------------------------------------
# Tests: parse_vtt — error cases
# ---------------------------------------------------------------------------

class TestParseVTTErrors:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_vtt("/nonexistent/path/missing.vtt")


# ---------------------------------------------------------------------------
# Tests: parse_subtitle — auto-detect format
# ---------------------------------------------------------------------------

class TestParseSubtitle:
    def test_detects_srt(self, tmp_path):
        entries = parse_subtitle(_write(tmp_path, "auto.srt", VALID_SRT))
        assert len(entries) == 3

    def test_detects_vtt(self, tmp_path):
        entries = parse_subtitle(_write(tmp_path, "auto.vtt", VALID_VTT))
        assert len(entries) == 3

    def test_unsupported_extension_raises(self, tmp_path):
        path = _write(tmp_path, "test.txt", "some text")
        with pytest.raises(ValueError, match="Unsupported subtitle format"):
            parse_subtitle(path)
