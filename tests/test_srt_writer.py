import re
import pytest
from pathlib import Path

from src.models import SubtitleEntry
from src.srt_writer import write_bilingual_srt, write_vietnamese_srt, format_timestamp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_pair(index: int, en: str, vi: str, start: float, end: float):
    en_entry = SubtitleEntry(index=index, start_time=start, end_time=end, text=en)
    vi_entry = SubtitleEntry(index=index, start_time=start, end_time=end, text=vi)
    return en_entry, vi_entry


def split_blocks(srt_content: str) -> list[str]:
    """Split SRT content into non-empty blocks."""
    return [b.strip() for b in srt_content.strip().split("\n\n") if b.strip()]


TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$"
)


# ---------------------------------------------------------------------------
# Tests: format_timestamp helper
# ---------------------------------------------------------------------------

class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0.0) == "00:00:00,000"

    def test_milliseconds(self):
        assert format_timestamp(0.5) == "00:00:00,500"

    def test_seconds(self):
        assert format_timestamp(3.0) == "00:00:03,000"

    def test_minutes(self):
        assert format_timestamp(90.0) == "00:01:30,000"

    def test_hours(self):
        assert format_timestamp(3661.0) == "01:01:01,000"

    def test_fractional_milliseconds_rounded(self):
        # 1.2345s → 1234ms → "00:00:01,234"
        assert format_timestamp(1.2345) == "00:00:01,234"

    def test_large_value(self):
        # 7384.999s = 2h 3m 4s 999ms
        assert format_timestamp(7384.999) == "02:03:04,999"


# ---------------------------------------------------------------------------
# Tests: bilingual SRT output
# ---------------------------------------------------------------------------

class TestBilingualSRT:
    def _write(self, tmp_path, en_entries, vi_entries) -> str:
        out = tmp_path / "bilingual.srt"
        write_bilingual_srt(en_entries, vi_entries, str(out))
        return out.read_text(encoding="utf-8")

    def test_creates_file(self, tmp_path):
        en, vi = make_pair(1, "Hello", "Xin chào", 0.0, 2.0)
        out = tmp_path / "out.srt"
        write_bilingual_srt([en], [vi], str(out))
        assert out.exists()

    def test_single_entry_structure(self, tmp_path):
        en, vi = make_pair(1, "Hello world", "Xin chào thế giới", 1.0, 3.5)
        content = self._write(tmp_path, [en], [vi])
        blocks = split_blocks(content)
        assert len(blocks) == 1

        lines = blocks[0].split("\n")
        assert lines[0] == "1"                         # index
        assert TIMECODE_RE.match(lines[1])             # timecode
        assert lines[2] == "Hello world"               # EN text
        assert lines[3] == "Xin chào thế giới"        # VI text

    def test_timecode_format(self, tmp_path):
        en, vi = make_pair(1, "Hi", "Xin chào", 65.123, 68.456)
        content = self._write(tmp_path, [en], [vi])
        lines = content.strip().split("\n")
        assert lines[1] == "00:01:05,123 --> 00:01:08,456"

    def test_multiple_entries_separated_by_blank_line(self, tmp_path):
        pairs = [make_pair(i, f"en {i}", f"vi {i}", float(i * 3), float(i * 3 + 2)) for i in range(1, 4)]
        en_entries = [p[0] for p in pairs]
        vi_entries = [p[1] for p in pairs]
        content = self._write(tmp_path, en_entries, vi_entries)
        blocks = split_blocks(content)
        assert len(blocks) == 3

    def test_index_preserved(self, tmp_path):
        en, vi = make_pair(42, "Test", "Kiểm tra", 10.0, 12.0)
        content = self._write(tmp_path, [en], [vi])
        assert split_blocks(content)[0].split("\n")[0] == "42"

    def test_unicode_vietnamese_diacritics(self, tmp_path):
        vi_text = "Học máy là lĩnh vực con của trí tuệ nhân tạo"
        en, vi = make_pair(1, "Machine learning is a subset of AI", vi_text, 0.0, 4.0)
        content = self._write(tmp_path, [en], [vi])
        assert vi_text in content

    def test_complex_vietnamese_diacritics(self, tmp_path):
        vi_text = "Độ dốc giảm dần được sử dụng để tối ưu hóa"
        en, vi = make_pair(1, "Gradient descent is used for optimization", vi_text, 5.0, 9.0)
        content = self._write(tmp_path, [en], [vi])
        assert vi_text in content

    def test_file_written_utf8(self, tmp_path):
        vi_text = "Mạng nơ-ron nhân tạo"
        en, vi = make_pair(1, "Neural network", vi_text, 0.0, 2.0)
        out = tmp_path / "out.srt"
        write_bilingual_srt([en], [vi], str(out))
        raw = out.read_bytes()
        assert vi_text.encode("utf-8") in raw

    def test_ends_with_trailing_newline(self, tmp_path):
        en, vi = make_pair(1, "Hello", "Xin chào", 0.0, 2.0)
        content = self._write(tmp_path, [en], [vi])
        assert content.endswith("\n")


# ---------------------------------------------------------------------------
# Tests: Vietnamese-only SRT output
# ---------------------------------------------------------------------------

class TestVietnameseSRT:
    def _write(self, tmp_path, en_entries, vi_entries) -> str:
        out = tmp_path / "vi_only.srt"
        write_vietnamese_srt(en_entries, vi_entries, str(out))
        return out.read_text(encoding="utf-8")

    def test_creates_file(self, tmp_path):
        en, vi = make_pair(1, "Hello", "Xin chào", 0.0, 2.0)
        out = tmp_path / "out.srt"
        write_vietnamese_srt([en], [vi], str(out))
        assert out.exists()

    def test_contains_only_vietnamese_text(self, tmp_path):
        en, vi = make_pair(1, "Hello world", "Xin chào thế giới", 0.0, 2.0)
        content = self._write(tmp_path, [en], [vi])
        assert "Xin chào thế giới" in content
        assert "Hello world" not in content

    def test_single_text_line_per_entry(self, tmp_path):
        en, vi = make_pair(1, "Hello world", "Xin chào thế giới", 0.0, 2.0)
        content = self._write(tmp_path, [en], [vi])
        blocks = split_blocks(content)
        lines = blocks[0].split("\n")
        # index + timecode + exactly 1 text line
        assert len(lines) == 3

    def test_timecode_preserved_from_english(self, tmp_path):
        en, vi = make_pair(1, "Hi", "Xin chào", 120.5, 124.75)
        content = self._write(tmp_path, [en], [vi])
        assert "00:02:00,500 --> 00:02:04,750" in content

    def test_unicode_preserved(self, tmp_path):
        vi_text = "Thuật toán tối ưu hóa ngẫu nhiên"
        en, vi = make_pair(1, "Stochastic optimization algorithm", vi_text, 0.0, 3.0)
        content = self._write(tmp_path, [en], [vi])
        assert vi_text in content

    def test_multiple_entries(self, tmp_path):
        pairs = [make_pair(i, f"en {i}", f"vi {i}", float(i * 3), float(i * 3 + 2)) for i in range(1, 5)]
        en_entries = [p[0] for p in pairs]
        vi_entries = [p[1] for p in pairs]
        content = self._write(tmp_path, en_entries, vi_entries)
        assert len(split_blocks(content)) == 4


# ---------------------------------------------------------------------------
# Tests: edge cases & validation
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_mismatched_lengths_raises(self, tmp_path):
        en = SubtitleEntry(1, 0.0, 2.0, "Hello")
        vi1 = SubtitleEntry(1, 0.0, 2.0, "Xin chào")
        vi2 = SubtitleEntry(2, 2.0, 4.0, "Thêm một")
        with pytest.raises(ValueError, match="same length"):
            write_bilingual_srt([en], [vi1, vi2], str(tmp_path / "out.srt"))

    def test_empty_list_creates_empty_file(self, tmp_path):
        out = tmp_path / "out.srt"
        write_bilingual_srt([], [], str(out))
        assert out.exists()
        assert out.read_text(encoding="utf-8") == ""

    def test_vi_only_empty_list(self, tmp_path):
        out = tmp_path / "out.srt"
        write_vietnamese_srt([], [], str(out))
        assert out.read_text(encoding="utf-8") == ""

    def test_output_directory_created_if_missing(self, tmp_path):
        out = tmp_path / "subdir" / "output.srt"
        en, vi = make_pair(1, "Hello", "Xin chào", 0.0, 2.0)
        write_bilingual_srt([en], [vi], str(out))
        assert out.exists()
