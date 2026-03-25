from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

from src.tts_engine import AudioClip

logger = logging.getLogger(__name__)


class StretchAction(str, Enum):
    STRETCHED = "stretched"   # ratio within [min, max] — time-stretched to target
    PADDED = "padded"         # ratio < min — audio kept, silence appended
    TOO_FAST = "too_fast"     # ratio > max — stretched but flagged for review


@dataclass
class StretchResult:
    file_path: str
    action: StretchAction
    speed_ratio: float
    warning: str | None


@dataclass
class StretchConfig:
    max_speed_ratio: float = 1.6
    min_speed_ratio: float = 0.75


class TimeStretcher:
    def __init__(self, config: StretchConfig | None = None):
        self.config = config or StretchConfig()

    def process(self, clip: AudioClip, output_path: str) -> StretchResult:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        ratio = clip.actual_duration / clip.target_duration
        logger.debug(
            "clip %d: actual=%.3fs target=%.3fs ratio=%.3f",
            clip.index, clip.actual_duration, clip.target_duration, ratio,
        )

        if ratio < self.config.min_speed_ratio:
            return self._pad_silence(clip, output_path, ratio)
        elif ratio > self.config.max_speed_ratio:
            return self._stretch(clip, output_path, ratio, too_fast=True)
        else:
            return self._stretch(clip, output_path, ratio, too_fast=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stretch(
        self, clip: AudioClip, output_path: str, ratio: float, too_fast: bool
    ) -> StretchResult:
        audio, sr = librosa.load(clip.file_path, sr=None, mono=True)

        stretched = librosa.effects.time_stretch(audio, rate=ratio)

        # Trim or pad by a few samples to hit exact target frame count
        target_frames = int(round(clip.target_duration * sr))
        if len(stretched) > target_frames:
            stretched = stretched[:target_frames]
        elif len(stretched) < target_frames:
            stretched = np.pad(stretched, (0, target_frames - len(stretched)))

        sf.write(output_path, stretched, sr, subtype="PCM_16")

        warning = None
        if too_fast:
            warning = (
                f"Speed ratio {ratio:.2f}x exceeds maximum {self.config.max_speed_ratio}x. "
                f"Options: (1) accept fast speech as-is, "
                f"(2) summarize/shorten the translated text and regenerate."
            )

        return StretchResult(
            file_path=output_path,
            action=StretchAction.TOO_FAST if too_fast else StretchAction.STRETCHED,
            speed_ratio=ratio,
            warning=warning,
        )

    def _pad_silence(
        self, clip: AudioClip, output_path: str, ratio: float
    ) -> StretchResult:
        audio, sr = sf.read(clip.file_path, dtype="int16")

        target_frames = int(round(clip.target_duration * sr))
        current_frames = len(audio)

        if current_frames < target_frames:
            pad_frames = target_frames - current_frames
            silence = np.zeros(pad_frames, dtype=np.int16)
            padded = np.concatenate([audio, silence])
        else:
            padded = audio[:target_frames]

        sf.write(output_path, padded, sr, subtype="PCM_16")

        return StretchResult(
            file_path=output_path,
            action=StretchAction.PADDED,
            speed_ratio=ratio,
            warning=None,
        )


def load_stretcher_from_config(config_path: str = "config/config.yaml") -> TimeStretcher:
    from src.config_loader import load_config

    cfg = load_config(config_path)
    stretch_config = StretchConfig(
        max_speed_ratio=cfg.get("time_stretch.max_speed_ratio", default=1.6),
        min_speed_ratio=cfg.get("time_stretch.min_speed_ratio", default=0.75),
    )
    return TimeStretcher(config=stretch_config)
