from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import soundfile as sf

from src.models import SubtitleEntry

logger = logging.getLogger(__name__)


@dataclass
class AudioClip:
    file_path: str
    actual_duration: float   # seconds, measured from WAV file
    target_duration: float   # seconds, from SRT slot (end_time - start_time)
    index: int
    start_time: float = 0.0  # seconds, SRT start_time — position on timeline


@dataclass
class TTSConfig:
    model_path: str
    speed: float = 1.0


ProgressCallback = Callable[[int, int, AudioClip], None]

_PIPER_CANDIDATES = ["piper", "venv/bin/piper"]


def _find_piper() -> str:
    for candidate in _PIPER_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise FileNotFoundError("piper executable not found. Install piper-tts first.")


class TTSEngine:
    def __init__(
        self,
        config: TTSConfig,
        output_dir: str | None = None,
    ):
        self.config = config
        self._output_dir = output_dir
        self._tmpdir: tempfile.TemporaryDirectory | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_clip(self, entry: SubtitleEntry) -> AudioClip:
        out_dir = self._ensure_output_dir()
        out_path = Path(out_dir) / f"clip_{entry.index:04d}.wav"
        self._run_piper(entry.text, str(out_path))
        actual_duration = self._measure_duration(str(out_path))
        target_duration = entry.end_time - entry.start_time
        return AudioClip(
            file_path=str(out_path),
            actual_duration=actual_duration,
            target_duration=target_duration,
            index=entry.index,
            start_time=entry.start_time,
        )

    def generate_all(
        self,
        entries: list[SubtitleEntry],
        progress_callback: ProgressCallback | None = None,
    ) -> list[AudioClip]:
        if not entries:
            return []

        clips: list[AudioClip] = []
        total = len(entries)

        for idx, entry in enumerate(entries):
            clip = self.generate_clip(entry)
            clips.append(clip)
            if progress_callback:
                progress_callback(idx + 1, total, clip)

        return clips

    def __del__(self):
        if self._tmpdir is not None:
            try:
                self._tmpdir.cleanup()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_output_dir(self) -> str:
        if self._output_dir:
            Path(self._output_dir).mkdir(parents=True, exist_ok=True)
            return self._output_dir
        if self._tmpdir is None:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="vietlearn_tts_")
        return self._tmpdir.name

    def _run_piper(self, text: str, output_path: str) -> None:
        piper = _find_piper()
        cmd = [
            piper,
            "--model", self.config.model_path,
            "--output_file", output_path,
        ]
        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Piper TTS failed (exit {result.returncode}): {result.stderr}"
            )
        logger.debug("Piper generated %s", output_path)

    def _measure_duration(self, wav_path: str) -> float:
        info = sf.info(wav_path)
        return info.frames / info.samplerate


def load_tts_engine_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> TTSEngine:
    from src.config_loader import load_config

    cfg = load_config(config_path)
    tts_config = TTSConfig(
        model_path=cfg.get("tts.model_path", default="piper_models/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"),
        speed=cfg.get("tts.speed", default=1.0),
    )
    return TTSEngine(config=tts_config, output_dir=output_dir)
