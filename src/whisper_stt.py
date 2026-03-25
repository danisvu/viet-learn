"""Whisper.cpp Speech-to-Text: transcribe audio files and write SRT output."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.models import SubtitleEntry

logger = logging.getLogger(__name__)

# pywhispercpp is an optional dependency — only required when WhisperSTT is
# actually used. The try/except lets the rest of the app import normally when
# the package is not installed, and allows tests to mock WhisperModel cleanly.
try:
    from pywhispercpp.model import Model as WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore[assignment,misc]

# Whisper.cpp timestamps are in units of 10 ms (centiseconds × 10).
# Dividing by 100 converts to seconds.
_WHISPER_TS_SCALE = 100.0


@dataclass
class WhisperConfig:
    """Configuration for WhisperSTT."""

    model: str = "large-v3-turbo"
    model_dir: str = "whisper_models"
    n_threads: int = 4
    language: str = "en"
    output_dir: str = "output/stt"


@dataclass
class STTResult:
    """Result returned by WhisperSTT.transcribe()."""

    srt_path: str
    entries: list[SubtitleEntry]
    audio_path: str


class WhisperSTT:
    """Transcribe an audio file to SRT using whisper.cpp (pywhispercpp).

    The Whisper model is loaded lazily on the first call to :meth:`transcribe`
    so that constructing the object never blocks the caller.
    """

    def __init__(self, config: WhisperConfig) -> None:
        self.config = config
        self._model = None  # lazy — loaded on first transcribe()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcribe(
        self,
        audio_path: str,
        output_path: str | None = None,
    ) -> STTResult:
        """Transcribe *audio_path* and write an SRT file.

        Args:
            audio_path: Path to the input audio file (WAV, MP3, …).
            output_path: Explicit destination SRT path. If None, a path is
                derived from *audio_path* inside ``config.output_dir``.

        Returns:
            STTResult with the SRT path, parsed SubtitleEntry list, and the
            original audio path.

        Raises:
            FileNotFoundError: If *audio_path* does not exist.
            ImportError: If pywhispercpp is not installed.
        """
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        srt_path = self._resolve_output_path(audio_path, output_path)
        Path(srt_path).parent.mkdir(parents=True, exist_ok=True)

        model = self._load_model()
        segments = model.transcribe(audio_path)

        entries = self._segments_to_entries(segments)
        self._write_srt(entries, srt_path)

        logger.info(
            "Transcription complete: %d segment(s) → %s", len(entries), srt_path
        )
        return STTResult(srt_path=srt_path, entries=entries, audio_path=audio_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self):
        """Return the cached WhisperModel, constructing it on first call."""
        if WhisperModel is None:
            raise ImportError(
                "pywhispercpp is not installed. "
                "Install it with: pip install pywhispercpp"
            )
        if self._model is None:
            self._model = WhisperModel(
                self.config.model,
                models_dir=self.config.model_dir,
                n_threads=self.config.n_threads,
                language=self.config.language,
            )
        return self._model

    def _segments_to_entries(self, segments) -> list[SubtitleEntry]:
        """Convert whisper.cpp segment objects to SubtitleEntry list.

        Skips segments whose text is empty or whitespace-only.
        Re-sequences indices from 1 so there are no gaps after filtering.
        """
        entries: list[SubtitleEntry] = []
        idx = 1
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            entries.append(
                SubtitleEntry(
                    index=idx,
                    start_time=seg.t0 / _WHISPER_TS_SCALE,
                    end_time=seg.t1 / _WHISPER_TS_SCALE,
                    text=text,
                )
            )
            idx += 1
        return entries

    def _write_srt(self, entries: list[SubtitleEntry], output_path: str) -> None:
        """Write *entries* to *output_path* in SRT format."""
        from src.srt_writer import format_timestamp

        blocks = [
            f"{e.index}\n"
            f"{format_timestamp(e.start_time)} --> {format_timestamp(e.end_time)}\n"
            f"{e.text}"
            for e in entries
        ]
        content = "\n\n".join(blocks)
        if content:
            content += "\n"
        Path(output_path).write_text(content, encoding="utf-8")

    def _resolve_output_path(self, audio_path: str, output_path: str | None) -> str:
        """Return the SRT output path, deriving it from *audio_path* if needed."""
        if output_path:
            return output_path
        stem = Path(audio_path).stem
        return str(Path(self.config.output_dir) / f"{stem}.srt")


def load_whisper_stt_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> WhisperSTT:
    """Create a WhisperSTT from a YAML config file.

    Args:
        config_path: Path to the YAML config file.
        output_dir: Override for the SRT output directory. If None, reads from
            the ``whisper.output_dir`` key in config.

    Returns:
        Configured WhisperSTT instance (model not yet loaded).
    """
    from src.config_loader import load_config

    cfg = load_config(config_path)
    whisper_cfg = WhisperConfig(
        model=cfg.get("whisper.model", default="large-v3-turbo"),
        model_dir=cfg.get("whisper.model_dir", default="whisper_models"),
        n_threads=cfg.get("whisper.n_threads", default=4),
        language=cfg.get("whisper.language", default="en"),
        output_dir=output_dir or cfg.get("whisper.output_dir", default="output/stt"),
    )
    return WhisperSTT(config=whisper_cfg)
