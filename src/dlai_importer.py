"""DeepLearning.AI file importer: validates, converts VTT→SRT, and copies files."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv"}
SUPPORTED_SUBTITLE_EXTENSIONS = {".srt", ".vtt"}


@dataclass
class ImportResult:
    """Result of importing a video + subtitle pair into the project."""

    video_path: str              # copied video path inside output_dir
    subtitle_path: str           # SRT path inside output_dir (converted if needed)
    subtitle_was_converted: bool  # True when VTT was converted to SRT
    original_video_path: str     # user-provided source video path
    original_subtitle_path: str  # user-provided source subtitle path


@dataclass
class DLAIImporterConfig:
    """Configuration for DLAIImporter."""

    output_dir: str = "output/imports"


class DLAIImporter:
    """Import DeepLearning.AI video + subtitle files into the project.

    Validates formats, converts VTT to SRT when necessary, and copies
    both files into the configured output directory.
    """

    def __init__(self, config: DLAIImporterConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def import_files(self, video_path: str, subtitle_path: str) -> ImportResult:
        """Validate, convert, and copy a video + subtitle pair.

        Args:
            video_path: Absolute or relative path to the video file.
            subtitle_path: Absolute or relative path to the .srt or .vtt file.

        Returns:
            ImportResult with paths to the copied/converted files.

        Raises:
            FileNotFoundError: If either source file does not exist.
            ValueError: If a file has an unsupported format.
        """
        self._validate_video(video_path)
        self._validate_subtitle(subtitle_path)

        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy video — preserve original filename
        copied_video = self._copy_file(video_path, str(out_dir))
        logger.info("Video copied to %s", copied_video)

        # Handle subtitle
        sub_ext = Path(subtitle_path).suffix.lower()
        if sub_ext == ".vtt":
            srt_name = Path(subtitle_path).stem + ".srt"
            srt_dest = str(out_dir / srt_name)
            self._convert_vtt_to_srt(subtitle_path, srt_dest)
            copied_subtitle = srt_dest
            was_converted = True
            logger.info("VTT converted to SRT at %s", copied_subtitle)
        else:
            copied_subtitle = self._copy_file(subtitle_path, str(out_dir))
            was_converted = False
            logger.info("SRT copied to %s", copied_subtitle)

        return ImportResult(
            video_path=copied_video,
            subtitle_path=copied_subtitle,
            subtitle_was_converted=was_converted,
            original_video_path=video_path,
            original_subtitle_path=subtitle_path,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_video(self, path: str) -> None:
        """Raise if video file is missing or has an unsupported extension."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Video file not found: {path}")
        if p.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported video format '{p.suffix}'. "
                f"Supported: {sorted(SUPPORTED_VIDEO_EXTENSIONS)}"
            )

    def _validate_subtitle(self, path: str) -> None:
        """Raise if subtitle file is missing or has an unsupported extension."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Subtitle file not found: {path}")
        if p.suffix.lower() not in SUPPORTED_SUBTITLE_EXTENSIONS:
            raise ValueError(
                f"Unsupported subtitle format '{p.suffix}'. "
                f"Supported: {sorted(SUPPORTED_SUBTITLE_EXTENSIONS)}"
            )

    def _convert_vtt_to_srt(self, vtt_path: str, srt_output_path: str) -> None:
        """Parse a VTT file and write it as an SRT file.

        Reuses srt_parser.parse_vtt for parsing and srt_writer.format_timestamp
        for producing proper SRT-format timestamps (HH:MM:SS,mmm).
        """
        from src.srt_parser import parse_vtt
        from src.srt_writer import format_timestamp

        entries = parse_vtt(vtt_path)
        blocks: list[str] = []
        for entry in entries:
            start_ts = format_timestamp(entry.start_time)
            end_ts = format_timestamp(entry.end_time)
            blocks.append(f"{entry.index}\n{start_ts} --> {end_ts}\n{entry.text}")

        content = "\n\n".join(blocks)
        if content:
            content += "\n"

        Path(srt_output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(srt_output_path).write_text(content, encoding="utf-8")

    def _copy_file(self, src: str, dest_dir: str) -> str:
        """Copy *src* into *dest_dir*, preserving the filename.

        Returns:
            Absolute path of the copied file.
        """
        dest = Path(dest_dir) / Path(src).name
        shutil.copy2(src, str(dest))
        return str(dest)


def load_dlai_importer_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> DLAIImporter:
    """Create a DLAIImporter from a YAML config file.

    Args:
        config_path: Path to the YAML config file.
        output_dir: Override for the output directory. If None, reads from config.

    Returns:
        Configured DLAIImporter instance.
    """
    from src.config_loader import load_config

    cfg = load_config(config_path)
    resolved_dir = output_dir or cfg.get("imports.output_dir", default="output/imports")
    return DLAIImporter(DLAIImporterConfig(output_dir=resolved_dir))
