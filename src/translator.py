from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Callable

import requests

from src.models import SubtitleEntry, GlossaryTerm, GlossaryMode

logger = logging.getLogger(__name__)


class OllamaAPIError(Exception):
    pass


@dataclass
class TranslatorConfig:
    base_url: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_delay: float = 0.1


ProgressCallback = Callable[[int, int, SubtitleEntry], None]


class Translator:
    def __init__(
        self,
        config: TranslatorConfig | None = None,
        glossary: list[GlossaryTerm] | None = None,
    ):
        self.config = config or TranslatorConfig()
        self.glossary = glossary or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate(
        self,
        entries: list[SubtitleEntry],
        progress_callback: ProgressCallback | None = None,
    ) -> list[SubtitleEntry]:
        if not entries:
            return []

        results: list[SubtitleEntry] = []
        total = len(entries)

        for idx, entry in enumerate(entries):
            if idx > 0 and self.config.batch_delay > 0:
                time.sleep(self.config.batch_delay)

            translated_text = self._translate_entry(entry)
            translated = SubtitleEntry(
                index=entry.index,
                start_time=entry.start_time,
                end_time=entry.end_time,
                text=translated_text,
            )
            results.append(translated)

            if progress_callback:
                progress_callback(idx + 1, total, translated)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _translate_entry(self, entry: SubtitleEntry) -> str:
        matched_terms = self._find_matching_terms(entry.text)
        prompt = self._build_prompt(entry.text, matched_terms)
        raw = self._call_ollama_with_retry(prompt)
        return raw.strip()

    def _find_matching_terms(self, text: str) -> list[GlossaryTerm]:
        text_lower = text.lower()
        return [
            term for term in self.glossary
            if term.english.lower() in text_lower
        ]

    def _build_prompt(self, text: str, matched_terms: list[GlossaryTerm]) -> str:
        lines = [
            "Translate the following English text to Vietnamese.",
            "Output ONLY the translation — no explanation, no notes, no alternatives.",
            "/no_think",
        ]

        if matched_terms:
            lines.append("\nGlossary rules for this translation:")
            for term in matched_terms:
                if term.mode == GlossaryMode.KEEP_ENGLISH:
                    lines.append(f'- Keep "{term.english}" as-is in English (do not translate it).')
                elif term.mode == GlossaryMode.REPLACE:
                    lines.append(f'- Translate "{term.english}" as "{term.vietnamese}".')
                elif term.mode == GlossaryMode.TRANSLATE_ANNOTATE:
                    lines.append(
                        f'- Translate "{term.english}" as "{term.vietnamese} ({term.english})".'
                    )

        lines.append(f"\nText:\n{text}")
        return "\n".join(lines)

    def _call_ollama_with_retry(self, prompt: str) -> str:
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
                logger.warning("Ollama API attempt %d/%d failed: %s", attempt, self.config.max_retries, exc)
                if attempt < self.config.max_retries and self.config.retry_delay > 0:
                    time.sleep(self.config.retry_delay)
            except requests.exceptions.RequestException as exc:
                raise OllamaAPIError(f"Ollama API error: {exc}") from exc

        raise OllamaAPIError(
            f"Ollama API failed after {self.config.max_retries} retries: {last_exc}"
        )


def load_translator_from_config(config_path: str = "config/config.yaml") -> Translator:
    from src.config_loader import load_config

    cfg = load_config(config_path)
    translator_config = TranslatorConfig(
        base_url=cfg.get("ollama.base_url", default="http://localhost:11434"),
        model=cfg.get("ollama.model", default="qwen3:8b"),
        timeout=cfg.get("ollama.timeout", default=60),
        max_retries=cfg.get("translator.max_retries", default=3),
        retry_delay=cfg.get("translator.retry_delay", default=1.0),
        batch_delay=cfg.get("translator.batch_delay", default=0.1),
    )
    return Translator(config=translator_config)
