"""Tests for FlashcardGenerator — extraction, parsing, export (.apkg + CSV)."""
from __future__ import annotations

import csv
import json
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.models import BilingualEntry
from src.flashcard_generator import (
    FlashcardConfig,
    FlashcardError,
    FlashcardGenerator,
    QAPair,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _entry(i: int, en: str = "", vi: str = "") -> BilingualEntry:
    return BilingualEntry(
        index=i,
        start=f"00:00:{i:02d},000",
        end=f"00:00:{i + 1:02d},000",
        text_en=en or f"English sentence {i}.",
        text_vi=vi or f"Câu tiếng Việt {i}.",
    )


def _make_entries(n: int = 5) -> list[BilingualEntry]:
    pairs = [
        ("Gradient descent minimizes the loss function.",
         "Gradient descent (giảm dần độ dốc) giúp tối thiểu hóa hàm mất mát."),
        ("The learning rate controls step size.",
         "Tốc độ học (learning rate) kiểm soát kích thước bước cập nhật."),
        ("Backpropagation computes gradients efficiently.",
         "Lan truyền ngược (backpropagation) tính gradient một cách hiệu quả."),
        ("Overfitting occurs when the model memorizes training data.",
         "Quá khớp (overfitting) xảy ra khi mô hình ghi nhớ dữ liệu huấn luyện."),
        ("A neural network has layers of neurons.",
         "Mạng nơ-ron (neural network) có nhiều lớp (layers) neuron."),
    ]
    return [_entry(i + 1, en, vi) for i, (en, vi) in enumerate(pairs[:n])]


def _pairs(n: int = 3) -> list[QAPair]:
    return [
        QAPair(
            question=f"Gradient descent là gì? (card {i})",
            answer=f"Thuật toán tối ưu hóa giảm theo hướng gradient. (card {i})",
            tags=["test"],
        )
        for i in range(n)
    ]


def _json_response(pairs: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "response": "```json\n" + json.dumps(pairs, ensure_ascii=False) + "\n```"
    }
    return resp


_SAMPLE_JSON_PAIRS = [
    {"question": "Gradient descent là gì?",
     "answer": "Thuật toán tối ưu hóa dựa trên hướng ngược của gradient."},
    {"question": "Learning rate ảnh hưởng đến gì?",
     "answer": "Kiểm soát kích thước bước cập nhật trọng số."},
    {"question": "Overfitting là gì?",
     "answer": "Mô hình ghi nhớ dữ liệu train và hoạt động kém trên dữ liệu mới."},
]


# ---------------------------------------------------------------------------
# TestFlashcardConfig
# ---------------------------------------------------------------------------

class TestFlashcardConfig:
    def test_default_base_url(self):
        assert FlashcardConfig().base_url == "http://localhost:11434"

    def test_default_model(self):
        assert FlashcardConfig().model == "qwen3:8b"

    def test_default_timeout_at_least_120(self):
        assert FlashcardConfig().timeout >= 120

    def test_default_max_retries(self):
        assert FlashcardConfig().max_retries >= 1

    def test_anki_ids_are_stable_integers(self):
        cfg = FlashcardConfig()
        assert isinstance(cfg.anki_deck_id, int)
        assert isinstance(cfg.anki_model_id, int)

    def test_anki_ids_differ(self):
        cfg = FlashcardConfig()
        assert cfg.anki_deck_id != cfg.anki_model_id


# ---------------------------------------------------------------------------
# TestQAPair
# ---------------------------------------------------------------------------

class TestQAPair:
    def test_stores_question_and_answer(self):
        p = QAPair(question="X là gì?", answer="X là Y.")
        assert p.question == "X là gì?"
        assert p.answer == "X là Y."

    def test_default_tags_empty(self):
        p = QAPair(question="Q", answer="A")
        assert p.tags == []

    def test_custom_tags(self):
        p = QAPair(question="Q", answer="A", tags=["ai", "ml"])
        assert "ai" in p.tags


# ---------------------------------------------------------------------------
# TestBuildTranscript
# ---------------------------------------------------------------------------

class TestBuildTranscript:
    def _gen(self) -> FlashcardGenerator:
        return FlashcardGenerator()

    def test_joins_vi_lines(self):
        result = self._gen()._build_transcript(_make_entries(3))
        assert "Gradient descent" in result
        assert "Tốc độ học" in result

    def test_skips_empty_vi(self):
        entries = [
            BilingualEntry(index=1, start="", end="", text_en="A", text_vi="Hello"),
            BilingualEntry(index=2, start="", end="", text_en="B", text_vi=""),
            BilingualEntry(index=3, start="", end="", text_en="C", text_vi="World"),
        ]
        result = self._gen()._build_transcript(entries)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_truncates_at_limit(self):
        gen = FlashcardGenerator(FlashcardConfig(max_transcript_chars=50))
        entries = [_entry(i, vi="a" * 20) for i in range(10)]
        result = gen._build_transcript(entries)
        assert "truncated" in result

    def test_no_truncation_within_limit(self):
        result = self._gen()._build_transcript(_make_entries(5))
        assert "truncated" not in result


# ---------------------------------------------------------------------------
# TestBuildPrompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def _gen(self) -> FlashcardGenerator:
        return FlashcardGenerator()

    def test_contains_title(self):
        p = self._gen()._build_prompt("text", "Intro to ML", 5, 20)
        assert "Intro to ML" in p

    def test_contains_transcript(self):
        p = self._gen()._build_prompt("gradient descent text", "", 5, 20)
        assert "gradient descent text" in p

    def test_contains_min_max_cards(self):
        p = self._gen()._build_prompt("text", "", 8, 15)
        assert "8" in p
        assert "15" in p

    def test_contains_no_think_directive(self):
        assert "/no_think" in self._gen()._build_prompt("text", "", 5, 20)

    def test_requests_json_output(self):
        p = self._gen()._build_prompt("text", "", 5, 20)
        assert "json" in p.lower()

    def test_fallback_title(self):
        p = self._gen()._build_prompt("text", "", 5, 20)
        assert "không có tiêu đề" in p

    def test_hoi_dap_keywords_in_prompt(self):
        p = self._gen()._build_prompt("text", "", 5, 20)
        assert "Hỏi:" in p or "question" in p.lower()


# ---------------------------------------------------------------------------
# TestTryJsonParse
# ---------------------------------------------------------------------------

class TestTryJsonParse:
    def _gen(self) -> FlashcardGenerator:
        return FlashcardGenerator()

    def test_parses_fenced_json(self):
        text = "```json\n" + json.dumps(_SAMPLE_JSON_PAIRS) + "\n```"
        result = self._gen()._try_json_parse(text, ["tag"])
        assert len(result) == 3

    def test_parses_bare_json_array(self):
        text = json.dumps(_SAMPLE_JSON_PAIRS)
        result = self._gen()._try_json_parse(text, [])
        assert len(result) == 3

    def test_returns_qa_pair_objects(self):
        text = "```json\n" + json.dumps(_SAMPLE_JSON_PAIRS[:1]) + "\n```"
        result = self._gen()._try_json_parse(text, [])
        assert isinstance(result[0], QAPair)

    def test_question_and_answer_populated(self):
        text = "```json\n" + json.dumps(_SAMPLE_JSON_PAIRS[:1]) + "\n```"
        result = self._gen()._try_json_parse(text, [])
        assert result[0].question == _SAMPLE_JSON_PAIRS[0]["question"]
        assert result[0].answer == _SAMPLE_JSON_PAIRS[0]["answer"]

    def test_tags_applied(self):
        text = "```json\n" + json.dumps(_SAMPLE_JSON_PAIRS[:1]) + "\n```"
        result = self._gen()._try_json_parse(text, ["lecture1"])
        assert "lecture1" in result[0].tags

    def test_skips_item_missing_question(self):
        data = [{"answer": "some answer"}]
        text = json.dumps(data)
        result = self._gen()._try_json_parse(text, [])
        assert len(result) == 0

    def test_skips_item_missing_answer(self):
        data = [{"question": "X là gì?"}]
        text = json.dumps(data)
        result = self._gen()._try_json_parse(text, [])
        assert len(result) == 0

    def test_returns_empty_on_invalid_json(self):
        result = self._gen()._try_json_parse("not json at all", [])
        assert result == []

    def test_returns_empty_on_no_array(self):
        result = self._gen()._try_json_parse('{"key": "value"}', [])
        assert result == []

    def test_strips_think_block_before_parse(self):
        raw = "<think>ignore</think>\n```json\n" + json.dumps(_SAMPLE_JSON_PAIRS) + "\n```"
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        result = self._gen()._try_json_parse(cleaned, [])
        assert len(result) == 3


# need re import
import re


# ---------------------------------------------------------------------------
# TestTryLineParse
# ---------------------------------------------------------------------------

class TestTryLineParse:
    def _gen(self) -> FlashcardGenerator:
        return FlashcardGenerator()

    def test_parses_hoi_dap_lines(self):
        text = "Hỏi: X là gì?\nĐáp: X là một khái niệm quan trọng."
        result = self._gen()._try_line_parse(text, [])
        assert len(result) == 1
        assert result[0].question == "X là gì?"
        assert result[0].answer == "X là một khái niệm quan trọng."

    def test_parses_multiple_pairs(self):
        text = (
            "Hỏi: Câu 1?\nĐáp: Trả lời 1.\n"
            "Hỏi: Câu 2?\nĐáp: Trả lời 2.\n"
        )
        result = self._gen()._try_line_parse(text, [])
        assert len(result) == 2

    def test_tags_applied(self):
        text = "Hỏi: Q?\nĐáp: A."
        result = self._gen()._try_line_parse(text, ["lec1"])
        assert "lec1" in result[0].tags

    def test_skips_orphan_dap(self):
        text = "Đáp: answer without question"
        result = self._gen()._try_line_parse(text, [])
        assert result == []

    def test_empty_text_returns_empty(self):
        assert self._gen()._try_line_parse("", []) == []

    def test_case_insensitive_prefix(self):
        text = "hỏi: question?\nđáp: answer."
        result = self._gen()._try_line_parse(text, [])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestExtractHappyPath
# ---------------------------------------------------------------------------

class TestExtractHappyPath:
    @patch("requests.post")
    def test_returns_list_of_qa_pairs(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        result = gen.extract(_make_entries(), title="Lecture 1")
        assert isinstance(result, list)
        assert all(isinstance(p, QAPair) for p in result)

    @patch("requests.post")
    def test_returns_correct_count(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        result = gen.extract(_make_entries())
        assert len(result) == 3

    @patch("requests.post")
    def test_question_content(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        result = gen.extract(_make_entries())
        questions = [p.question for p in result]
        assert "Gradient descent là gì?" in questions

    @patch("requests.post")
    def test_title_tag_applied(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        result = gen.extract(_make_entries(), title="ML Basics")
        assert all("ML Basics" in p.tags for p in result)

    @patch("requests.post")
    def test_calls_ollama_once(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        FlashcardGenerator().extract(_make_entries())
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_payload_model_name(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        cfg = FlashcardConfig(model="qwen3:30b")
        FlashcardGenerator(cfg).extract(_make_entries())
        assert mock_post.call_args[1]["json"]["model"] == "qwen3:30b"

    @patch("requests.post")
    def test_payload_stream_false(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        FlashcardGenerator().extract(_make_entries())
        assert mock_post.call_args[1]["json"]["stream"] is False

    @patch("requests.post")
    def test_transcript_in_prompt(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        entries = [_entry(1, vi="Giảm dần độ dốc là...")]
        FlashcardGenerator().extract(entries)
        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "Giảm dần độ dốc là..." in prompt

    @patch("requests.post")
    def test_fallback_to_line_parse(self, mock_post):
        """When model returns 'Hỏi/Đáp' format instead of JSON."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "response": "Hỏi: X là gì?\nĐáp: X là khái niệm quan trọng."
        }
        mock_post.return_value = resp
        gen = FlashcardGenerator()
        result = gen.extract(_make_entries())
        assert len(result) == 1
        assert result[0].question == "X là gì?"

    @patch("requests.post")
    def test_think_block_stripped(self, mock_post):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "response": "<think>reasoning</think>\n```json\n"
                        + json.dumps(_SAMPLE_JSON_PAIRS) + "\n```"
        }
        mock_post.return_value = resp
        result = FlashcardGenerator().extract(_make_entries())
        assert len(result) == 3

    def test_raises_on_empty_entries(self):
        with pytest.raises(ValueError, match="empty"):
            FlashcardGenerator().extract([])

    @patch("requests.post")
    def test_min_max_cards_in_prompt(self, mock_post):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        FlashcardGenerator().extract(_make_entries(), min_cards=7, max_cards=25)
        prompt = mock_post.call_args[1]["json"]["prompt"]
        assert "7" in prompt
        assert "25" in prompt


# ---------------------------------------------------------------------------
# TestExtractRetry
# ---------------------------------------------------------------------------

class TestExtractRetry:
    @patch("requests.post")
    @patch("time.sleep")
    def test_retries_on_timeout(self, mock_sleep, mock_post):
        mock_post.side_effect = [
            requests.exceptions.Timeout(),
            _json_response(_SAMPLE_JSON_PAIRS),
        ]
        cfg = FlashcardConfig(max_retries=2, retry_delay=0.0)
        result = FlashcardGenerator(cfg).extract(_make_entries())
        assert len(result) == 3
        assert mock_post.call_count == 2

    @patch("requests.post")
    @patch("time.sleep")
    def test_raises_after_all_retries(self, mock_sleep, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()
        cfg = FlashcardConfig(max_retries=2, retry_delay=0.0)
        with pytest.raises(FlashcardError):
            FlashcardGenerator(cfg).extract(_make_entries())

    @patch("requests.post")
    def test_http_error_raises_immediately(self, mock_post):
        mock_post.side_effect = requests.exceptions.HTTPError("403")
        with pytest.raises(FlashcardError):
            FlashcardGenerator().extract(_make_entries())

    @patch("requests.post")
    @patch("time.sleep")
    def test_retry_count_matches_config(self, mock_sleep, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError()
        cfg = FlashcardConfig(max_retries=3, retry_delay=0.0)
        with pytest.raises(FlashcardError):
            FlashcardGenerator(cfg).extract(_make_entries())
        assert mock_post.call_count == 3


# ---------------------------------------------------------------------------
# TestExportApkg
# ---------------------------------------------------------------------------

class TestExportApkg:
    def test_creates_apkg_file(self, tmp_path):
        path = str(tmp_path / "deck.apkg")
        FlashcardGenerator().export_apkg(_pairs(3), path)
        assert os.path.exists(path)

    def test_apkg_is_valid_zip(self, tmp_path):
        path = str(tmp_path / "deck.apkg")
        FlashcardGenerator().export_apkg(_pairs(3), path)
        assert zipfile.is_zipfile(path)

    def test_apkg_contains_collection_db(self, tmp_path):
        path = str(tmp_path / "deck.apkg")
        FlashcardGenerator().export_apkg(_pairs(3), path)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        assert any("collection" in n for n in names)

    def test_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "output" / "anki" / "deck.apkg")
        FlashcardGenerator().export_apkg(_pairs(2), path)
        assert os.path.exists(path)

    def test_raises_on_empty_pairs(self, tmp_path):
        with pytest.raises(ValueError, match="empty"):
            FlashcardGenerator().export_apkg([], str(tmp_path / "out.apkg"))

    def test_custom_deck_name(self, tmp_path):
        """Deck name shouldn't crash export."""
        path = str(tmp_path / "deck.apkg")
        FlashcardGenerator().export_apkg(_pairs(2), path, deck_name="ML Vocabulary")
        assert os.path.exists(path)

    def test_single_card(self, tmp_path):
        path = str(tmp_path / "single.apkg")
        FlashcardGenerator().export_apkg(_pairs(1), path)
        assert zipfile.is_zipfile(path)

    def test_many_cards(self, tmp_path):
        path = str(tmp_path / "many.apkg")
        FlashcardGenerator().export_apkg(_pairs(50), path)
        assert os.path.exists(path)

    def test_stable_anki_ids(self, tmp_path):
        """Two exports with same config should use same deck/model IDs."""
        cfg1 = FlashcardConfig()
        cfg2 = FlashcardConfig()
        assert cfg1.anki_deck_id == cfg2.anki_deck_id
        assert cfg1.anki_model_id == cfg2.anki_model_id


# ---------------------------------------------------------------------------
# TestExportCsv
# ---------------------------------------------------------------------------

class TestExportCsv:
    def test_creates_csv_file(self, tmp_path):
        path = str(tmp_path / "cards.csv")
        FlashcardGenerator().export_csv(_pairs(3), path)
        assert os.path.exists(path)

    def test_csv_has_header(self, tmp_path):
        path = str(tmp_path / "cards.csv")
        FlashcardGenerator().export_csv(_pairs(3), path)
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
        assert header == ["Question", "Answer"]

    def test_csv_row_count(self, tmp_path):
        path = str(tmp_path / "cards.csv")
        FlashcardGenerator().export_csv(_pairs(5), path)
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=";"))
        assert len(rows) == 6  # header + 5 data rows

    def test_csv_content(self, tmp_path):
        path = str(tmp_path / "cards.csv")
        pairs = [QAPair("Gradient descent là gì?", "Thuật toán tối ưu hóa.")]
        FlashcardGenerator().export_csv(pairs, path)
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=";"))
        assert rows[1][0] == "Gradient descent là gì?"
        assert rows[1][1] == "Thuật toán tối ưu hóa."

    def test_csv_utf8_vietnamese(self, tmp_path):
        path = str(tmp_path / "vi.csv")
        pairs = [QAPair("Mạng nơ-ron là gì?", "Hệ thống các neuron nhân tạo.")]
        FlashcardGenerator().export_csv(pairs, path)
        content = open(path, encoding="utf-8").read()
        assert "Mạng nơ-ron" in content

    def test_csv_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "deep" / "cards.csv")
        FlashcardGenerator().export_csv(_pairs(2), path)
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# TestFullFlow
# ---------------------------------------------------------------------------

class TestFullFlow:
    @patch("requests.post")
    def test_extract_then_export_apkg(self, mock_post, tmp_path):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        pairs = gen.extract(_make_entries(), title="Deep Learning")
        path = str(tmp_path / "dl.apkg")
        gen.export_apkg(pairs, path, deck_name="Deep Learning")
        assert zipfile.is_zipfile(path)

    @patch("requests.post")
    def test_extract_then_export_csv(self, mock_post, tmp_path):
        mock_post.return_value = _json_response(_SAMPLE_JSON_PAIRS)
        gen = FlashcardGenerator()
        pairs = gen.extract(_make_entries(), title="ML")
        path = str(tmp_path / "ml.csv")
        gen.export_csv(pairs, path)
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter=";"))
        assert len(rows) == len(pairs) + 1  # header + data
