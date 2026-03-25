import time
import pytest
import requests

from unittest.mock import MagicMock, patch, call
from src.models import SubtitleEntry, GlossaryTerm, GlossaryMode
from src.translator import Translator, TranslatorConfig, OllamaAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(index: int, text: str) -> SubtitleEntry:
    return SubtitleEntry(index=index, start_time=float(index), end_time=float(index + 2), text=text)


def mock_ollama_response(translated_text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"response": translated_text}
    resp.raise_for_status.return_value = None
    return resp


DEFAULT_CONFIG = TranslatorConfig(
    base_url="http://localhost:11434",
    model="qwen3:8b",
    timeout=10,
    max_retries=3,
    retry_delay=0.0,
    batch_delay=0.0,
)


# ---------------------------------------------------------------------------
# Tests: danh sách rỗng
# ---------------------------------------------------------------------------

class TestEmptyList:
    def test_returns_empty_list(self):
        t = Translator(config=DEFAULT_CONFIG)
        result = t.translate([])
        assert result == []

    def test_no_api_calls_on_empty(self):
        t = Translator(config=DEFAULT_CONFIG)
        with patch("requests.post") as mock_post:
            t.translate([])
            mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: mock Ollama API response
# ---------------------------------------------------------------------------

class TestOllamaAPICall:
    def test_translates_single_entry(self):
        entries = [make_entry(1, "Hello world")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào thế giới")
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert len(result) == 1
        assert result[0].text == "Xin chào thế giới"

    def test_preserves_index_and_timestamps(self):
        entries = [make_entry(5, "Deep learning")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Học sâu")
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert result[0].index == 5
        assert result[0].start_time == 5.0
        assert result[0].end_time == 7.0

    def test_translates_multiple_entries(self):
        entries = [make_entry(i, f"sentence {i}") for i in range(3)]
        translations = ["câu 0", "câu 1", "câu 2"]
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [mock_ollama_response(t) for t in translations]
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert [r.text for r in result] == translations

    def test_api_called_with_correct_url(self):
        entries = [make_entry(1, "Hello")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào")
            t = Translator(config=DEFAULT_CONFIG)
            t.translate(entries)

        url = mock_post.call_args[0][0]
        assert url == "http://localhost:11434/api/generate"

    def test_api_called_with_correct_model(self):
        entries = [make_entry(1, "Hello")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào")
            t = Translator(config=DEFAULT_CONFIG)
            t.translate(entries)

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "qwen3:8b"

    def test_prompt_instructs_translation_only(self):
        entries = [make_entry(1, "Hello")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào")
            t = Translator(config=DEFAULT_CONFIG)
            t.translate(entries)

        payload = mock_post.call_args[1]["json"]
        prompt = payload["prompt"]
        # Prompt phải yêu cầu chỉ output bản dịch, không giải thích
        assert "Hello" in prompt
        assert any(kw in prompt.lower() for kw in ["only", "chỉ", "translation", "dịch", "không", "no explanation"])

    def test_strips_whitespace_from_response(self):
        entries = [make_entry(1, "Hello")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("  Xin chào  \n")
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert result[0].text == "Xin chào"


# ---------------------------------------------------------------------------
# Tests: retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_timeout(self):
        entries = [make_entry(1, "Hello")]
        success = mock_ollama_response("Xin chào")
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                requests.exceptions.Timeout(),
                success,
            ]
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert result[0].text == "Xin chào"
        assert mock_post.call_count == 2

    def test_retries_on_connection_error(self):
        entries = [make_entry(1, "Hello")]
        success = mock_ollama_response("Xin chào")
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                requests.exceptions.ConnectionError(),
                success,
            ]
            t = Translator(config=DEFAULT_CONFIG)
            result = t.translate(entries)

        assert result[0].text == "Xin chào"

    def test_raises_after_max_retries_exceeded(self):
        entries = [make_entry(1, "Hello")]
        cfg = TranslatorConfig(
            base_url="http://localhost:11434",
            model="qwen3:8b",
            timeout=10,
            max_retries=2,
            retry_delay=0.0,
            batch_delay=0.0,
        )
        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()
            t = Translator(config=cfg)
            with pytest.raises(OllamaAPIError):
                t.translate(entries)

        assert mock_post.call_count == 2

    def test_raises_on_http_error(self):
        entries = [make_entry(1, "Hello")]
        err_resp = MagicMock()
        err_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        with patch("requests.post") as mock_post:
            mock_post.return_value = err_resp
            t = Translator(config=DEFAULT_CONFIG)
            with pytest.raises(OllamaAPIError):
                t.translate(entries)


# ---------------------------------------------------------------------------
# Tests: glossary replacement
# ---------------------------------------------------------------------------

class TestGlossaryReplacement:
    def _translate_with_glossary(self, text: str, glossary: list, api_response: str) -> str:
        entries = [make_entry(1, text)]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response(api_response)
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            result = t.translate(entries)
        return result[0].text

    def test_keep_english_mode_keeps_term_in_prompt(self):
        glossary = [GlossaryTerm("gradient descent", "", GlossaryMode.KEEP_ENGLISH)]
        entries = [make_entry(1, "Use gradient descent to train")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Dùng gradient descent để huấn luyện")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "gradient descent" in prompt

    def test_replace_mode_injects_vietnamese_into_prompt(self):
        glossary = [GlossaryTerm("epoch", "vòng huấn luyện", GlossaryMode.REPLACE)]
        entries = [make_entry(1, "Run for 10 epochs")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Chạy 10 vòng huấn luyện")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "epoch" in prompt
        assert "vòng huấn luyện" in prompt

    def test_translate_annotate_mode_injects_format_into_prompt(self):
        glossary = [GlossaryTerm("overfitting", "học quá khớp", GlossaryMode.TRANSLATE_ANNOTATE)]
        entries = [make_entry(1, "This causes overfitting")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Điều này gây ra học quá khớp (overfitting)")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "overfitting" in prompt
        assert "học quá khớp" in prompt

    def test_no_glossary_injection_when_term_not_in_text(self):
        glossary = [GlossaryTerm("backpropagation", "lan truyền ngược", GlossaryMode.REPLACE)]
        entries = [make_entry(1, "Hello world")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào thế giới")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "backpropagation" not in prompt

    def test_glossary_matching_is_case_insensitive(self):
        glossary = [GlossaryTerm("gradient descent", "", GlossaryMode.KEEP_ENGLISH)]
        entries = [make_entry(1, "Use Gradient Descent here")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Dùng Gradient Descent ở đây")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "gradient descent" in prompt.lower()

    def test_multiple_glossary_terms_in_one_entry(self):
        glossary = [
            GlossaryTerm("loss function", "hàm mất mát", GlossaryMode.REPLACE),
            GlossaryTerm("batch", "", GlossaryMode.KEEP_ENGLISH),
        ]
        entries = [make_entry(1, "Compute loss function over each batch")]
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Tính hàm mất mát trên mỗi batch")
            t = Translator(config=DEFAULT_CONFIG, glossary=glossary)
            t.translate(entries)

        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "hàm mất mát" in prompt
        assert "batch" in prompt


# ---------------------------------------------------------------------------
# Tests: progress callback
# ---------------------------------------------------------------------------

class TestProgressCallback:
    def test_callback_called_for_each_entry(self):
        entries = [make_entry(i, f"text {i}") for i in range(3)]
        progress_calls = []

        def on_progress(current: int, total: int, entry: SubtitleEntry):
            progress_calls.append((current, total))

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [mock_ollama_response(f"text {i}") for i in range(3)]
            t = Translator(config=DEFAULT_CONFIG)
            t.translate(entries, progress_callback=on_progress)

        assert progress_calls == [(1, 3), (2, 3), (3, 3)]

    def test_callback_receives_translated_entry(self):
        entries = [make_entry(1, "Hello")]
        received_entries = []

        def on_progress(current, total, entry):
            received_entries.append(entry)

        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào")
            t = Translator(config=DEFAULT_CONFIG)
            t.translate(entries, progress_callback=on_progress)

        assert received_entries[0].text == "Xin chào"


# ---------------------------------------------------------------------------
# Tests: batch delay
# ---------------------------------------------------------------------------

class TestBatchDelay:
    def test_batch_delay_applied_between_entries(self):
        entries = [make_entry(i, f"text {i}") for i in range(2)]
        cfg = TranslatorConfig(
            base_url="http://localhost:11434",
            model="qwen3:8b",
            timeout=10,
            max_retries=3,
            retry_delay=0.0,
            batch_delay=0.05,
        )
        with patch("requests.post") as mock_post:
            mock_post.side_effect = [mock_ollama_response(f"câu {i}") for i in range(2)]
            t = Translator(config=cfg)
            start = time.monotonic()
            t.translate(entries)
            elapsed = time.monotonic() - start

        # 1 delay between 2 entries = at least 0.05s
        assert elapsed >= 0.05

    def test_no_delay_for_single_entry(self):
        entries = [make_entry(1, "Hello")]
        cfg = TranslatorConfig(
            base_url="http://localhost:11434",
            model="qwen3:8b",
            timeout=10,
            max_retries=3,
            retry_delay=0.0,
            batch_delay=1.0,  # would be slow if applied before first entry
        )
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_ollama_response("Xin chào")
            t = Translator(config=cfg)
            start = time.monotonic()
            t.translate(entries)
            elapsed = time.monotonic() - start

        # delay only applied BETWEEN entries, not before first
        assert elapsed < 0.5
