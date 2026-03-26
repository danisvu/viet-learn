"""Summarizer — generates a structured Vietnamese Markdown summary from a
translated transcript using Qwen3-8B via Ollama."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests

from src.models import BilingualEntry

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class SummarizerConfig:
    """Runtime configuration for the Summarizer."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    timeout: int = 180          # summaries take longer than single entries
    max_retries: int = 2
    retry_delay: float = 2.0
    # Transcript is truncated to this length before being sent to the model.
    # ~40 000 chars ≈ 10 000 tokens — well within Qwen3-8B's 32k context.
    max_transcript_chars: int = 40_000


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SummarizerError(Exception):
    """Raised when Ollama call fails or returns unusable output."""


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------

_SECTION_PROMPT = """\
Bạn là trợ lý học thuật. Hãy tạo tóm tắt bài giảng từ bản dịch tiếng Việt.
Output ONLY valid Markdown — không giải thích thêm, không lời mở đầu.
/no_think

Cấu trúc bắt buộc (giữ nguyên các heading H2):

## Tổng quan
(2-4 câu mô tả toàn bộ bài giảng)

## Khái niệm chính
(danh sách bullet — mỗi khái niệm 1 dòng)

## Định nghĩa & Công thức
(danh sách definition — **thuật ngữ**: giải thích; công thức dùng code block)

## Code & Ví dụ
(giữ nguyên code bằng tiếng Anh trong ```code block```)

## Điểm cần nhớ
(3-7 bullet quan trọng nhất để ôn tập)

---
Tiêu đề bài giảng: {title}

Transcript (Tiếng Việt):
{transcript}
"""


class Summarizer:
    """Generates a structured Vietnamese Markdown summary from a bilingual
    transcript by calling Qwen3-8B through the Ollama API.

    Usage::

        cfg = SummarizerConfig(base_url="http://localhost:11434")
        s = Summarizer(cfg)
        md = s.summarize(entries, title="Intro to Backpropagation")
        s.save(md, "output/summary.md")
    """

    def __init__(self, config: SummarizerConfig | None = None) -> None:
        self.config = config or SummarizerConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarize(
        self,
        entries: list[BilingualEntry],
        title: str = "",
    ) -> str:
        """Generate a Markdown summary for *entries*.

        Args:
            entries: Bilingual subtitle entries (must have ``text_vi`` set).
            title:   Optional lecture title included in the prompt.

        Returns:
            Markdown string with the five structured sections.

        Raises:
            SummarizerError: If the Ollama call fails after all retries.
            ValueError: If *entries* is empty.
        """
        if not entries:
            raise ValueError("entries must not be empty")

        transcript = self._build_transcript(entries)
        prompt = self._build_prompt(transcript, title)
        raw = self._call_ollama(prompt)
        return self._clean_output(raw)

    def save(self, markdown: str, path: str) -> None:
        """Write *markdown* to *path* (creates parent directories as needed).

        Args:
            markdown: Markdown string returned by :meth:`summarize`.
            path:     Destination file path (should end with ``.md``).
        """
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(markdown)
        log.info("Summary saved to %s (%d chars)", path, len(markdown))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_transcript(self, entries: list[BilingualEntry]) -> str:
        """Concatenate Vietnamese lines, optionally preserve code-like lines."""
        lines: list[str] = []
        for e in entries:
            vi = e.text_vi.strip()
            if vi:
                lines.append(vi)
        text = "\n".join(lines)
        if len(text) > self.config.max_transcript_chars:
            text = text[: self.config.max_transcript_chars]
            text += "\n\n[... transcript truncated ...]"
            log.warning(
                "Transcript truncated to %d chars for summarization",
                self.config.max_transcript_chars,
            )
        return text

    def _build_prompt(self, transcript: str, title: str) -> str:
        return _SECTION_PROMPT.format(
            title=title or "(không có tiêu đề)",
            transcript=transcript,
        )

    def _clean_output(self, raw: str) -> str:
        """Strip any <think> blocks and leading/trailing whitespace."""
        # Qwen3 sometimes wraps reasoning in <think>...</think>
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
        return cleaned.strip()

    def _call_ollama(self, prompt: str) -> str:
        """POST to /api/generate with retry logic.

        Raises:
            SummarizerError: After all retries are exhausted.
        """
        url = f"{self.config.base_url}/api/generate"
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }
        last_exc: Exception = RuntimeError("No attempts made")

        for attempt in range(1, self.config.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.config.timeout)
                resp.raise_for_status()
                return resp.json()["response"]
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_exc = exc
                log.warning(
                    "Summarizer attempt %d/%d failed: %s",
                    attempt,
                    self.config.max_retries,
                    exc,
                )
                if attempt < self.config.max_retries and self.config.retry_delay > 0:
                    time.sleep(self.config.retry_delay)
            except requests.exceptions.RequestException as exc:
                raise SummarizerError(f"Ollama API error: {exc}") from exc

        raise SummarizerError(
            f"Summarizer failed after {self.config.max_retries} retries: {last_exc}"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def load_summarizer_from_config(config_path: str = "config/config.yaml") -> Summarizer:
    """Create a :class:`Summarizer` from the project config file."""
    from src.config_loader import load_config

    cfg = load_config(config_path)
    summarizer_config = SummarizerConfig(
        base_url=cfg.get("ollama.base_url", default="http://localhost:11434"),
        model=cfg.get("ollama.model", default="qwen3:8b"),
        timeout=cfg.get("ollama.timeout", default=180),
    )
    return Summarizer(summarizer_config)
