"""Flashcard generator — scan transcript with Qwen3-8B, extract Q&A pairs,
export Anki deck (.apkg) via genanki."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

import genanki
import requests

from src.models import BilingualEntry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config & data types
# ---------------------------------------------------------------------------

@dataclass
class FlashcardConfig:
    """Runtime configuration for the FlashcardGenerator."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    timeout: int = 180
    max_retries: int = 2
    retry_delay: float = 2.0
    # Transcript chars sent to the model per chunk (fits in 32k context)
    max_transcript_chars: int = 40_000
    # Anki deck/model IDs — must be stable integers; chosen arbitrarily but
    # fixed so re-exports produce the same deck identity.
    anki_deck_id: int = 1_234_567_890
    anki_model_id: int = 9_876_543_210


@dataclass
class QAPair:
    """One extracted question-answer pair."""

    question: str
    answer: str
    # Optional tag set (e.g. lecture title, topic)
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FlashcardError(Exception):
    """Raised when Ollama call fails or JSON parsing fails."""


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
Bạn là chuyên gia tạo flashcard học thuật. \
Từ bản dịch tiếng Việt dưới đây, hãy trích xuất các cặp câu hỏi-câu trả lời \
để luyện tập kiến thức kỹ thuật.

Quy tắc:
- Mỗi câu hỏi bắt đầu bằng "Hỏi:" và câu trả lời bắt đầu bằng "Đáp:"
- Câu hỏi dạng: "X là gì?", "X hoạt động như thế nào?", "Tại sao X?", "So sánh X và Y"
- Câu trả lời ngắn gọn (1-4 câu), giữ thuật ngữ kỹ thuật tiếng Anh trong ngoặc
- Trả về ĐÚNG định dạng JSON sau — không thêm bất kỳ text nào ngoài JSON:
/no_think

```json
[
  {{"question": "...", "answer": "..."}},
  {{"question": "...", "answer": "..."}}
]
```

Số lượng flashcard: tối thiểu {min_cards}, tối đa {max_cards}.
Tiêu đề bài giảng: {title}

Transcript:
{transcript}
"""


# ---------------------------------------------------------------------------
# FlashcardGenerator
# ---------------------------------------------------------------------------

class FlashcardGenerator:
    """Extract Q&A flashcards from a bilingual transcript and export to Anki.

    Usage::

        cfg = FlashcardConfig()
        gen = FlashcardGenerator(cfg)
        pairs = gen.extract(entries, title="Backpropagation")
        gen.export_apkg(pairs, "output/backprop.apkg", deck_name="Backpropagation")
    """

    def __init__(self, config: FlashcardConfig | None = None) -> None:
        self.config = config or FlashcardConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        entries: list[BilingualEntry],
        title: str = "",
        min_cards: int = 5,
        max_cards: int = 20,
    ) -> list[QAPair]:
        """Call Qwen3-8B and return extracted Q&A pairs.

        Args:
            entries:   Bilingual subtitle entries (``text_vi`` must be set).
            title:     Lecture title embedded in the prompt.
            min_cards: Minimum cards to request from the model.
            max_cards: Maximum cards to request from the model.

        Returns:
            List of :class:`QAPair` objects (may be empty if model returns none).

        Raises:
            ValueError: If *entries* is empty.
            FlashcardError: On Ollama failure or unrecoverable JSON parse error.
        """
        if not entries:
            raise ValueError("entries must not be empty")

        transcript = self._build_transcript(entries)
        prompt = self._build_prompt(transcript, title, min_cards, max_cards)
        raw = self._call_ollama(prompt)
        return self._parse_pairs(raw, tags=[title] if title else [])

    def export_apkg(
        self,
        pairs: list[QAPair],
        path: str,
        deck_name: str = "VietLearn",
    ) -> None:
        """Write *pairs* to an Anki package file at *path*.

        Args:
            pairs:     Q&A pairs (from :meth:`extract`).
            path:      Destination .apkg path; parent directories are created.
            deck_name: Display name of the Anki deck.

        Raises:
            ValueError: If *pairs* is empty.
        """
        if not pairs:
            raise ValueError("pairs must not be empty")

        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        model = self._build_anki_model()
        deck = genanki.Deck(self.config.anki_deck_id, deck_name)

        for pair in pairs:
            # Anki tags must not contain spaces — replace with underscore
            safe_tags = [t.replace(" ", "_") for t in pair.tags]
            note = genanki.Note(
                model=model,
                fields=[pair.question, pair.answer],
                tags=safe_tags,
            )
            deck.add_note(note)

        pkg = genanki.Package(deck)
        pkg.write_to_file(path)
        log.info("Exported %d cards to %s", len(pairs), path)

    def export_csv(self, pairs: list[QAPair], path: str) -> None:
        """Write *pairs* to a CSV file (UTF-8, semicolon-separated).

        Columns: Question, Answer
        Compatible with Anki's plain-text import.
        """
        import csv, os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["Question", "Answer"])
            for p in pairs:
                writer.writerow([p.question, p.answer])
        log.info("Exported %d cards to CSV %s", len(pairs), path)

    # ------------------------------------------------------------------
    # Private helpers — transcript & prompt
    # ------------------------------------------------------------------

    def _build_transcript(self, entries: list[BilingualEntry]) -> str:
        lines = [e.text_vi.strip() for e in entries if e.text_vi.strip()]
        text = "\n".join(lines)
        if len(text) > self.config.max_transcript_chars:
            text = text[: self.config.max_transcript_chars]
            text += "\n\n[... transcript truncated ...]"
            log.warning("Transcript truncated for flashcard extraction")
        return text

    def _build_prompt(
        self, transcript: str, title: str, min_cards: int, max_cards: int
    ) -> str:
        return _EXTRACT_PROMPT.format(
            title=title or "(không có tiêu đề)",
            transcript=transcript,
            min_cards=min_cards,
            max_cards=max_cards,
        )

    # ------------------------------------------------------------------
    # Private helpers — parsing
    # ------------------------------------------------------------------

    def _parse_pairs(self, raw: str, tags: list[str]) -> list[QAPair]:
        """Extract Q&A list from model output.

        Tries two strategies in order:
        1. Parse JSON array from the response (preferred).
        2. Fallback: scan for "Hỏi:" / "Đáp:" line pairs.
        """
        # Strip <think> blocks (Qwen3 chain-of-thought)
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)

        pairs = self._try_json_parse(cleaned, tags)
        if pairs:
            return pairs

        log.warning("JSON parse failed; falling back to line-based extraction")
        return self._try_line_parse(cleaned, tags)

    def _try_json_parse(self, text: str, tags: list[str]) -> list[QAPair]:
        """Find the first JSON array in *text* and parse it."""
        # Accept both ```json ... ``` fenced blocks and bare arrays
        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if not match:
            match = re.search(r"(\[.*?\])", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
            pairs: list[QAPair] = []
            for item in data:
                q = str(item.get("question", "")).strip()
                a = str(item.get("answer", "")).strip()
                if q and a:
                    pairs.append(QAPair(question=q, answer=a, tags=list(tags)))
            return pairs
        except (json.JSONDecodeError, AttributeError, TypeError) as exc:
            log.debug("JSON parse attempt failed: %s", exc)
            return []

    def _try_line_parse(self, text: str, tags: list[str]) -> list[QAPair]:
        """Scan text for 'Hỏi: ...' / 'Đáp: ...' line pairs."""
        pairs: list[QAPair] = []
        current_q: str | None = None
        for line in text.splitlines():
            line = line.strip()
            if line.lower().startswith("hỏi:"):
                current_q = line[4:].strip()
            elif line.lower().startswith("đáp:") and current_q is not None:
                answer = line[4:].strip()
                if current_q and answer:
                    pairs.append(QAPair(question=current_q, answer=answer, tags=list(tags)))
                current_q = None
        return pairs

    # ------------------------------------------------------------------
    # Private helpers — Ollama
    # ------------------------------------------------------------------

    def _call_ollama(self, prompt: str) -> str:
        url = f"{self.config.base_url}/api/generate"
        payload = {"model": self.config.model, "prompt": prompt, "stream": False}
        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(1, self.config.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.config.timeout)
                resp.raise_for_status()
                return resp.json()["response"]
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                log.warning("FlashcardGenerator attempt %d/%d failed: %s",
                            attempt, self.config.max_retries, exc)
                if attempt < self.config.max_retries and self.config.retry_delay > 0:
                    time.sleep(self.config.retry_delay)
            except requests.exceptions.RequestException as exc:
                raise FlashcardError(f"Ollama API error: {exc}") from exc

        raise FlashcardError(
            f"FlashcardGenerator failed after {self.config.max_retries} retries: {last_exc}"
        )

    # ------------------------------------------------------------------
    # Private helpers — Anki model
    # ------------------------------------------------------------------

    def _build_anki_model(self) -> genanki.Model:
        return genanki.Model(
            self.config.anki_model_id,
            "VietLearn Basic",
            fields=[
                {"name": "Question"},
                {"name": "Answer"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "<div class='question'>{{Question}}</div>",
                    "afmt": (
                        "{{FrontSide}}"
                        "<hr id='answer'>"
                        "<div class='answer'>{{Answer}}</div>"
                    ),
                },
            ],
            css=(
                ".card { font-family: Arial, sans-serif; font-size: 16px; "
                "text-align: left; color: #222; background: #fff; padding: 20px; }"
                ".question { font-weight: bold; margin-bottom: 8px; }"
                ".answer { color: #1a5276; }"
            ),
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def load_flashcard_generator_from_config(
    config_path: str = "config/config.yaml",
) -> FlashcardGenerator:
    """Create a :class:`FlashcardGenerator` from the project config file."""
    from src.config_loader import load_config

    cfg = load_config(config_path)
    fc_config = FlashcardConfig(
        base_url=cfg.get("ollama.base_url", default="http://localhost:11434"),
        model=cfg.get("ollama.model", default="qwen3:8b"),
        timeout=cfg.get("ollama.timeout", default=180),
    )
    return FlashcardGenerator(fc_config)
