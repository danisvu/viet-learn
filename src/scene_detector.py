"""FFmpeg-based scene change detector.

Runs a single FFmpeg pass with the ``select='gt(scene,THRESHOLD)'`` filter
combined with ``showinfo`` to detect scene changes and extract one image frame
per detected cut.

Usage::

    from src.config_loader import load_config
    from src.scene_detector import SceneDetector

    cfg = load_config("config/config.yaml")
    detector = SceneDetector(cfg)
    frames = detector.detect("lecture.mp4")
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from src.config_loader import Config
from src.models import FrameInfo

logger = logging.getLogger(__name__)

# Matches one showinfo output line and captures n (0-based selected-frame index)
# and pts_time (timestamp in seconds).
# Example:
#   [Parsed_showinfo_1 @ 0x...] n:   0 pts:      0 pts_time:0       pos: ...
_SHOWINFO_RE = re.compile(r"\]\s*n:\s*(\d+).*?pts_time:([\d.]+)")


class SceneDetector:
    """Detect scene changes in a video using FFmpeg and extract frame images.

    Configuration keys (all under ``scene.*`` in config.yaml):

    * ``threshold`` – scene-change sensitivity in [0, 1]. Higher = fewer cuts.
      Default 0.3.
    * ``output_dir`` – default directory for frame images.
    * ``format`` – image format, ``jpg`` or ``png``.
    """

    def __init__(self, config: Config) -> None:
        self.threshold: float = float(config.get("scene.threshold", 0.3))
        self.output_dir = Path(config.get("scene.output_dir", "output/frames"))
        self.fmt: str = config.get("scene.format", "jpg")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        video_path: str | Path,
        output_dir: Path | None = None,
    ) -> list[FrameInfo]:
        """Detect scene changes and extract one frame image per cut.

        Args:
            video_path: Path to the input video file.
            output_dir: Directory where frame images are saved.
                        Falls back to ``config.scene.output_dir``.

        Returns:
            List of :class:`~src.models.FrameInfo` sorted by timestamp.
            Returns an empty list if FFmpeg is unavailable or no scenes found.
        """
        video_path = Path(video_path)
        frames_dir = output_dir or self.output_dir
        frames_dir.mkdir(parents=True, exist_ok=True)

        cmd = self._build_cmd(video_path, frames_dir)
        logger.debug("Running FFmpeg scene detection: %s", " ".join(cmd))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            logger.error("ffmpeg not found — install FFmpeg and ensure it is on PATH")
            return []

        if result.returncode != 0:
            logger.warning(
                "FFmpeg exited with code %d — frame extraction may be incomplete",
                result.returncode,
            )

        frames = self._parse_showinfo(result.stderr, frames_dir)
        logger.info(
            "Scene detection complete: %d frame(s) found in '%s'",
            len(frames),
            video_path.name,
        )
        return frames

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_cmd(self, video_path: Path, frames_dir: Path) -> list[str]:
        """Construct the FFmpeg command list."""
        vf = f"select='gt(scene,{self.threshold})',showinfo"
        frame_pattern = str(frames_dir / f"frame%04d.{self.fmt}")
        return [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", vf,
            "-vsync", "vfr",
            "-an",              # strip audio — we only want images
            frame_pattern,
        ]

    def _parse_showinfo(self, stderr: str, frames_dir: Path) -> list[FrameInfo]:
        """Parse FFmpeg showinfo stderr output into FrameInfo objects.

        FFmpeg numbers selected frames 0-based (the ``n:`` field in showinfo).
        The saved image filenames are 1-based (frame0001.jpg …), so we add 1.
        """
        frames: list[FrameInfo] = []
        for match in _SHOWINFO_RE.finditer(stderr):
            n = int(match.group(1))          # 0-based index among selected frames
            pts_time = float(match.group(2))
            index = n + 1                     # 1-based → matches frame%04d filename
            frame_path = frames_dir / f"frame{index:04d}.{self.fmt}"
            frames.append(
                FrameInfo(
                    frame_index=index,
                    timestamp=pts_time,
                    frame_path=str(frame_path),
                )
            )

        return sorted(frames, key=lambda f: f.timestamp)
