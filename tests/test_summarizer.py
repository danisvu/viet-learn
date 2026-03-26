"""Tests for Summarizer — prompt building, output cleaning, save, Ollama mock."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.models import BilingualEntry
from src.summarizer import Summarizer, SummarizerConfig, SummarizerError

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _entry(index: int, en: str, vi: str) -> BilingualEntry:
    return BilingualEntry(
        index=index,
        start=f"00:00:{index:02d},000",
        end=f"00:00:{index + 1:02d},000",
        text_en=en,
        text_vi=vi,
    )


def _make_entries(n: int = 5) -> list[BilingualEntry]:
    pairs = [
        ("Gradient descent minimizes the loss function.", "Giảm dần độ dốc giúp tối thiểu hóa hàm mất mát."),
        ("The learning rate controls step size.", "Tốc độ học kiểm soát kích thước bước."),
        ("Backpropagation computes gradients efficiently.", "Lan truyền ngược tính gradient một cách hiệu quả."),
        ("Here is sample code:\ndef train(model, data):\n    loss = model(data)", "Đây là code mẫu:\ndef train(model, data):\n    loss = model(data)"),
        ("Overfitting occurs when the model memorizes training data.", "Quá khớp xảy ra khi mô hình ghi nhớ dữ liệu huấn luyện."),
    ]
    return [_entry(i + 1, en, vi) for i, (en, vi) in enumerate(pairs[:n])]


_MOCK_MD = """\
## Tổng quan
Bài giảng giới thiệu thuật toán gradient descent và lan truyền ngược.

## Khái niệm chính
- Gradient descent
- Backpropagation
- Learning rate

## Định nghĩa & Công thức
**Gradient descent**: thuật toán tối ưu hóa giảm dần theo chiều gradient.

## Code & Ví dụ
```python
def train(model, data):
    loss = model(data)
```

## Điểm cần nhớ
- Tốc độ học ảnh hưởng đến hội tụ
- Quá khớp cần điều chỉnh regularization
"""


def _mock_resp(text: str = _MOCK_MD) -> MagicMock:
    """Build a mock requests.Response that returns *text* as Ollama response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"response": text}
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# TestSummarizerConfig
# ---------------------------------------------------------------------------

class TestSummarizerConfig:
    def test_default_base_url(self):
        cfg = SummarizerConfig()
        assert cfg.base_url == "http://localhost:11434"

    def test_default_model(self):
        cfg = SummarizerConfig()
        assert cfg.model == "qwen3:8b"

    def test_default_timeout_at_least_120(self):
        cfg = SummarizerConfig()
        assert cfg.timeout >= 120

    def test_default_max_retries(self):
        cfg = SummarizerConfig()
        assert cfg.max_retries >= 1

    def test_default_max_transcript_chars(self):
        cfg = SummarizerConfig()
        assert cfg.max_transcript_chars > 0

    def test_custom_values(self):
        cfg = SummarizerConfig(base_url="http://192.168.1.1:11434", model="qwen3:30b")
        assert cfg.base_url == "http://192.168.1.1:11434"
        assert cfg.model == "qwen3:30b"


# ---------------------------------------------------------------------------
# TestBuildTranscript
# ---------------------------------------------------------------------------

class TestBuildTranscript:
    def _s(self) -> Summarizer:
        return Summarizer(SummarizerConfig())

    def test_joins_vi_lines(self):
        entries = _make_entries(3)
        result = self._s()._build_transcript(entries)
        assert "Giảm dần độ dốc" in result
        assert "Tốc độ học" in result

    def test_skips_empty_vi(self):
        entries = [
            _entry(1, "Hello", "Xin chào"),
            _entry(2, "World", ""),  # empty VI
            _entry(3, "Bye", "Tạm biệt"),
        ]
        result = self._s()._build_transcript(entries)
        assert result.count("\n") == 1  # only 2 lines joined

    def test_truncates_long_transcript(self):
        cfg = SummarizerConfig(max_transcript_chars=50)
        s = Summarizer(cfg)
        entries = [_entry(i, "x", "a" * 20) for i in range(10)]
        result = s._build_transcript(entries)
        assert len(result) <= 50 + len("\n\n[... transcript truncated ...]")
        assert "truncated" in result

    def test_no_truncation_within_limit(self):
        entries = _make_entries(5)
        result = self._s()._build_transcript(entries)
        assert "truncated" not in result

    def test_all_entries_represented(self):
        entries = _make_entries(5)
        result = self._s()._build_transcript(entries)
        for e in entries:
            if e.text_vi:
                assert e.text_vi.strip() in result


# ---------------------------------------------------------------------------
# TestBuildPrompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def _s(self) -> Summarizer:
        return Summarizer()

    def test_prompt_contains_title(self):
        p = self._s()._build_prompt("some transcript", "Intro to ML")
        assert "Intro to ML" in p

    def test_prompt_contains_transcript(self):
        p = self._s()._build_prompt("gradient descent là...", "")
        assert "gradient descent là..." in p

    def test_prompt_has_required_headings(self):
        p = self._s()._build_prompt("text", "title")
        for heading in [
            "## Tổng quan",
            "## Khái niệm chính",
            "## Định nghĩa & Công thức",
            "## Code & Ví dụ",
            "## Điểm cần nhớ",
        ]:
            assert heading in p

    def test_prompt_has_no_think_directive(self):
        p = self._s()._build_prompt("text", "title")
        assert "/no_think" in p

    def test_fallback_title_when_empty(self):
        p = self._s()._build_prompt("text", "")
        assert "không có tiêu đề" in p

    def test_prompt_instructs_markdown_only(self):
        p = self._s()._build_prompt("text", "title")
        assert "Markdown" in p


# ---------------------------------------------------------------------------
# TestCleanOutput
# ---------------------------------------------------------------------------

class TestCleanOutput:
    def _s(self) -> Summarizer:
        return Summarizer()

    def test_strips_think_block(self):
        raw = "<think>some reasoning here</think>\n## Tổng quan\nNội dung"
        result = self._s()._clean_output(raw)
        assert "<think>" not in result
        assert "## Tổng quan" in result

    def test_strips_multiline_think_block(self):
        raw = "<think>\nline1\nline2\n</think>\n## Tổng quan"
        result = self._s()._clean_output(raw)
        assert "line1" not in result

    def test_strips_leading_whitespace(self):
        raw = "\n\n  ## Tổng quan\nnội dung"
        result = self._s()._clean_output(raw)
        assert result.startswith("##")

    def test_preserves_content_after_think(self):
        raw = "<think>ignore</think>## Khái niệm chính\n- item"
        result = self._s()._clean_output(raw)
        assert "- item" in result

    def test_no_think_block_passes_through(self):
        raw = "## Tổng quan\nNội dung bình thường"
        assert self._s()._clean_output(raw) == raw


# ---------------------------------------------------------------------------
# TestSummarizeHappyPath
# ---------------------------------------------------------------------------

class TestSummarizeHappyPath:
    @patch("requests.post")
    def test_returns_string(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        result = s.summarize(_make_entries(), title="Lecture 1")
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("requests.post")
    def test_contains_required_sections(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        result = s.summarize(_make_entries(), title="Lecture 1")
        for section in [
            "## Tổng quan",
            "## Khái niệm chính",
            "## Định nghĩa & Công thức",
            "## Code & Ví dụ",
            "## Điểm cần nhớ",
        ]:
            assert section in result

    @patch("requests.post")
    def test_calls_ollama_once_on_success(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        s.summarize(_make_entries())
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_sends_to_correct_url(self, mock_post):
        mock_post.return_value = _mock_resp()
        cfg = SummarizerConfig(base_url="http://localhost:11434")
        s = Summarizer(cfg)
        s.summarize(_make_entries())
        url = mock_post.call_args[0][0]
        assert url == "http://localhost:11434/api/generate"

    @patch("requests.post")
    def test_payload_contains_model(self, mock_post):
        mock_post.return_value = _mock_resp()
        cfg = SummarizerConfig(model="qwen3:30b")
        s = Summarizer(cfg)
        s.summarize(_make_entries())
        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "qwen3:30b"

    @patch("requests.post")
    def test_payload_stream_false(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        s.summarize(_make_entries())
        payload = mock_post.call_args[1]["json"]
        assert payload["stream"] is False

    @patch("requests.post")
    def test_title_in_prompt(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        s.summarize(_make_entries(), title="Deep Learning 101")
        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "Deep Learning 101" in prompt

    @patch("requests.post")
    def test_transcript_in_prompt(self, mock_post):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        entries = [_entry(1, "Hello", "Xin chào thế giới")]
        s.summarize(entries, title="Test")
        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "Xin chào thế giới" in prompt

    @patch("requests.post")
    def test_think_block_stripped_from_result(self, mock_post):
        mock_post.return_value = _mock_resp(
            "<think>reasoning</think>\n" + _MOCK_MD
        )
        s = Summarizer()
        result = s.summarize(_make_entries())
        assert "<think>" not in result

    def test_raises_value_error_for_empty_entries(self):
        s = Summarizer()
        with pytest.raises(ValueError, match="empty"):
            s.summarize([])


# ---------------------------------------------------------------------------
# TestSummarizeRetry
# ---------------------------------------------------------------------------

class TestSummarizeRetry:
    @patch("requests.post")
    @patch("time.sleep")
    def test_retries_on_timeout(self, mock_sleep, mock_post):
        mock_post.side_effect = [
            requests.exceptions.Timeout("timeout"),
            _mock_resp(),
        ]
        cfg = SummarizerConfig(max_retries=2, retry_delay=0.0)
        s = Summarizer(cfg)
        result = s.summarize(_make_entries())
        assert "## Tổng quan" in result
        assert mock_post.call_count == 2

    @patch("requests.post")
    @patch("time.sleep")
    def test_retries_on_connection_error(self, mock_sleep, mock_post):
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("refused"),
            _mock_resp(),
        ]
        cfg = SummarizerConfig(max_retries=2, retry_delay=0.0)
        s = Summarizer(cfg)
        result = s.summarize(_make_entries())
        assert isinstance(result, str)

    @patch("requests.post")
    @patch("time.sleep")
    def test_raises_after_all_retries(self, mock_sleep, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("always timeout")
        cfg = SummarizerConfig(max_retries=2, retry_delay=0.0)
        s = Summarizer(cfg)
        with pytest.raises(SummarizerError):
            s.summarize(_make_entries())

    @patch("requests.post")
    def test_http_error_raises_immediately(self, mock_post):
        mock_post.side_effect = requests.exceptions.HTTPError("403")
        s = Summarizer(SummarizerConfig(max_retries=3))
        with pytest.raises(SummarizerError):
            s.summarize(_make_entries())

    @patch("requests.post")
    @patch("time.sleep")
    def test_retry_count_matches_config(self, mock_sleep, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        cfg = SummarizerConfig(max_retries=3, retry_delay=0.0)
        s = Summarizer(cfg)
        with pytest.raises(SummarizerError):
            s.summarize(_make_entries())
        assert mock_post.call_count == 3


# ---------------------------------------------------------------------------
# TestSave
# ---------------------------------------------------------------------------

class TestSave:
    def test_creates_file(self, tmp_path):
        s = Summarizer()
        path = str(tmp_path / "summary.md")
        s.save(_MOCK_MD, path)
        assert os.path.exists(path)

    def test_file_content_matches(self, tmp_path):
        s = Summarizer()
        path = str(tmp_path / "summary.md")
        s.save(_MOCK_MD, path)
        content = open(path, encoding="utf-8").read()
        assert content == _MOCK_MD

    def test_creates_parent_dirs(self, tmp_path):
        s = Summarizer()
        path = str(tmp_path / "sub" / "deep" / "summary.md")
        s.save(_MOCK_MD, path)
        assert os.path.exists(path)

    def test_utf8_encoding_preserved(self, tmp_path):
        s = Summarizer()
        md = "## Tổng quan\nGiảm dần độ dốc — mạng nơ-ron — tích phân"
        path = str(tmp_path / "vi.md")
        s.save(md, path)
        content = open(path, encoding="utf-8").read()
        assert "Giảm dần độ dốc" in content
        assert "mạng nơ-ron" in content

    def test_overwrites_existing_file(self, tmp_path):
        s = Summarizer()
        path = str(tmp_path / "out.md")
        s.save("old content", path)
        s.save("new content", path)
        assert open(path).read() == "new content"

    def test_md_extension_not_enforced(self, tmp_path):
        """save() should work with any extension."""
        s = Summarizer()
        path = str(tmp_path / "notes.txt")
        s.save("content", path)
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# TestSummarizeAndSave (integration-style, fully mocked)
# ---------------------------------------------------------------------------

class TestSummarizeAndSave:
    @patch("requests.post")
    def test_full_flow_produces_valid_md_file(self, mock_post, tmp_path):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        entries = _make_entries(5)
        md = s.summarize(entries, title="Backpropagation Deep Dive")
        path = str(tmp_path / "output" / "summary.md")
        s.save(md, path)

        content = open(path, encoding="utf-8").read()
        assert "## Tổng quan" in content
        assert len(content) > 50

    @patch("requests.post")
    def test_code_block_preserved_in_result(self, mock_post, tmp_path):
        """Mock returns a response that contains a code block."""
        mock_post.return_value = _mock_resp(_MOCK_MD)
        s = Summarizer()
        md = s.summarize(_make_entries())
        assert "```" in md

    @patch("requests.post")
    def test_save_path_with_spaces(self, mock_post, tmp_path):
        mock_post.return_value = _mock_resp()
        s = Summarizer()
        md = s.summarize(_make_entries())
        path = str(tmp_path / "my lectures" / "summary.md")
        s.save(md, path)
        assert os.path.exists(path)
