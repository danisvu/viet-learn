"""YouTube video and subtitle downloader using yt-dlp."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import yt_dlp

from src.models import DownloadResult

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]  # (current, total, title)


@dataclass
class YouTubeDownloaderConfig:
    """Configuration for YouTubeDownloader."""

    output_dir: str
    format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
    subtitle_langs: list[str] = field(default_factory=lambda: ["en"])
    subtitle_format: str = "srt"
    quiet: bool = True
    no_warnings: bool = True


class YouTubeDownloader:
    """Download YouTube videos and subtitles via yt-dlp."""

    def __init__(self, config: YouTubeDownloaderConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        url: str,
        progress_callback: ProgressCallback | None = None,
        ytdlp_hooks: list | None = None,
    ) -> list[DownloadResult]:
        """Download video(s) from *url* and return a list of DownloadResult.

        Args:
            url: YouTube video or playlist URL.
            progress_callback: Optional callable receiving (current, total, title).

        Returns:
            List of DownloadResult, one per successfully downloaded video.
        """
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        params = self._build_ydl_params()
        if ytdlp_hooks:
            params["progress_hooks"] = ytdlp_hooks

        with yt_dlp.YoutubeDL(params) as ydl:
            info = ydl.extract_info(url, download=True)

        entries = self._extract_entries(info)
        total = len(entries)
        results: list[DownloadResult] = []

        for idx, entry in enumerate(entries, start=1):
            result = self._make_result(entry)
            results.append(result)
            logger.info("Downloaded [%d/%d]: %s", idx, total, result.title)
            if progress_callback is not None:
                progress_callback(idx, total, result.title)

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ydl_params(self) -> dict:
        """Map YouTubeDownloaderConfig to a yt-dlp params dict."""
        return {
            "format": self.config.format,
            "outtmpl": os.path.join(self.config.output_dir, "%(title)s [%(id)s].%(ext)s"),
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": self.config.subtitle_langs,
            "subtitlesformat": self.config.subtitle_format,
            "noplaylist": False,
            "ignoreerrors": True,
            "quiet": self.config.quiet,
            "no_warnings": self.config.no_warnings,
        }

    def _extract_entries(self, info: dict) -> list[dict]:
        """Return a flat list of video entry dicts, filtering out None entries.

        Handles single video, playlist, and multi_video result types.
        """
        if info.get("_type") in ("playlist", "multi_video"):
            raw = info.get("entries") or []
            return [e for e in raw if e is not None]
        return [info]

    def _make_result(self, entry_info: dict) -> DownloadResult:
        """Build a DownloadResult from a single yt-dlp entry info dict."""
        video_id = entry_info.get("id", "")
        title = entry_info.get("title", "")
        ext = entry_info.get("ext", "mp4")
        webpage_url = entry_info.get("webpage_url", "")

        # Reconstruct the video file path using outtmpl pattern
        video_filename = f"{title} [{video_id}].{ext}"
        video_path = os.path.join(self.config.output_dir, video_filename)

        subtitle_path, subtitle_fallback, srt_not_found = self._detect_subtitle_status(entry_info)

        return DownloadResult(
            video_id=video_id,
            title=title,
            video_path=video_path,
            subtitle_path=subtitle_path,
            subtitle_fallback=subtitle_fallback,
            srt_not_found=srt_not_found,
            webpage_url=webpage_url,
        )

    def _detect_subtitle_status(
        self, entry_info: dict
    ) -> tuple[str | None, bool, bool]:
        """Determine subtitle path and status flags from entry_info.

        Returns:
            (subtitle_path, subtitle_fallback, srt_not_found)
        """
        requested = entry_info.get("requested_subtitles") or {}

        # Find the first matching language from our preference list
        lang: str | None = None
        for candidate in self.config.subtitle_langs:
            if candidate in requested:
                lang = candidate
                break

        if lang is None:
            # No subtitle in any requested language
            return None, False, True

        sub_info = requested[lang]
        filepath = sub_info.get("filepath")

        if not filepath or not os.path.exists(filepath):
            # File path present in dict but not on disk
            return None, False, True

        # Determine if this is creator-provided or auto-generated
        creator_langs: set[str] = set(entry_info.get("subtitles") or {})
        subtitle_fallback = lang not in creator_langs

        return filepath, subtitle_fallback, False


def load_youtube_downloader_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> YouTubeDownloader:
    """Create a YouTubeDownloader from a YAML config file.

    Args:
        config_path: Path to the YAML config file.
        output_dir: Override for the output directory. If None, reads from config.

    Returns:
        Configured YouTubeDownloader instance.
    """
    from src.config_loader import load_config

    cfg = load_config(config_path)

    resolved_output_dir = output_dir or cfg.get(
        "download.output_dir", default="output/downloads"
    )

    dl_config = YouTubeDownloaderConfig(
        output_dir=resolved_output_dir,
        format=cfg.get(
            "download.format",
            default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        ),
        subtitle_langs=cfg.get("download.subtitle_langs", default=["en"]),
        subtitle_format=cfg.get("download.subtitle_format", default="srt"),
        quiet=cfg.get("download.quiet", default=True),
        no_warnings=cfg.get("download.no_warnings", default=True),
    )
    return YouTubeDownloader(config=dl_config)
