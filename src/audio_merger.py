from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from src.tts_engine import AudioClip

logger = logging.getLogger(__name__)


@dataclass
class MergerConfig:
    original_volume: float = 0.15
    vi_volume: float = 1.0


def assemble_audio(
    clips: list[AudioClip],
    total_duration: float,
    output_path: str,
    sample_rate: int = 22050,
) -> str:
    """Place each clip at its start_time on a silence track of total_duration."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    total_frames = int(round(total_duration * sample_rate))
    track = np.zeros(total_frames, dtype=np.int16)

    for clip in clips:
        data, sr = sf.read(clip.file_path, dtype="int16")
        if sr != sample_rate:
            # simple resample by repeating/dropping — accurate resampler not needed here
            import librosa
            data_f = data.astype(np.float32) / 32768.0
            data_f = librosa.resample(data_f, orig_sr=sr, target_sr=sample_rate)
            data = (data_f * 32767).astype(np.int16)

        start_frame = int(round(clip.start_time * sample_rate))
        end_frame = min(start_frame + len(data), total_frames)
        copy_len = end_frame - start_frame
        if copy_len > 0:
            track[start_frame:end_frame] = data[:copy_len]

    sf.write(output_path, track, sample_rate, subtype="PCM_16")
    return output_path


class AudioMerger:
    def __init__(self, config: MergerConfig | None = None):
        self.config = config or MergerConfig()

    def merge_video(
        self,
        video_path: str,
        vi_audio_path: str,
        output_path: str,
    ) -> None:
        """Merge video with Vietnamese audio track via FFmpeg."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        vol_en = self.config.original_volume
        vol_vi = self.config.vi_volume
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", vi_audio_path,
            "-filter_complex",
            f"[1:a]volume={vol_vi}[vi];[0:a]volume={vol_en}[en]",
            "-map", "0:v",
            "-map", "[en]",
            "-map", "[vi]",
            "-c:v", "copy",
            output_path,
        ]
        logger.debug("FFmpeg merge: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg merge failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

    def export_mp3(self, vi_audio_path: str, output_path: str) -> None:
        """Export Vietnamese audio track as standalone MP3."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-i", vi_audio_path,
            "-q:a", "2",
            output_path,
        ]
        logger.debug("FFmpeg mp3 export: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg mp3 export failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )


def load_merger_from_config(config_path: str = "config/config.yaml") -> AudioMerger:
    from src.config_loader import load_config

    cfg = load_config(config_path)
    merger_config = MergerConfig(
        original_volume=cfg.get("audio.original_volume", default=0.15),
        vi_volume=cfg.get("audio.vi_volume", default=1.0),
    )
    return AudioMerger(config=merger_config)
