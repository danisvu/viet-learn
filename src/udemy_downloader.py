"""Udemy video downloader via yt-dlp with browser cookies and DRM detection."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

from src.models import DownloadResult

logger = logging.getLogger(__name__)

# Keywords that identify a DRM / access-denied failure (case-insensitive).
_DRM_MARKERS = ("403", "drm", "forbidden")


@dataclass
class UdemyDownloaderConfig:
    """Configuration for UdemyDownloader."""

    output_dir: str
    browser: str = "chrome"
    format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
    subtitle_langs: list[str] = field(default_factory=lambda: ["en"])
    subtitle_format: str = "srt"
    quiet: bool = True
    no_warnings: bool = True


@dataclass
class UdemyDownloadResult:
    """Result of a single Udemy download attempt.

    When *drm_blocked* is True the video is DRM-protected (HTTP 403) and the
    caller should fall back to BlackHole audio capture.  In that case
    *download_result* is None.
    """

    drm_blocked: bool
    download_result: DownloadResult | None


class UdemyDownloader:
    """Download a Udemy lecture using yt-dlp + browser cookies.

    If yt-dlp receives an HTTP 403 / DRM error the downloader returns a result
    with ``drm_blocked=True`` instead of raising, so the caller can switch to
    the BlackHole audio-capture fallback path.
    """

    def __init__(self, config: UdemyDownloaderConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(self, url: str) -> UdemyDownloadResult:
        """Attempt to download a Udemy lecture.

        Args:
            url: Full Udemy lecture URL.

        Returns:
            UdemyDownloadResult — check ``drm_blocked`` before using
            ``download_result``.

        Raises:
            yt_dlp.utils.DownloadError: For non-DRM download failures.
            Exception: Any other unexpected error.
        """
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        params = self._build_ydl_params(url)

        try:
            with yt_dlp.YoutubeDL(params) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            if self._is_drm_error(exc):
                logger.warning("DRM/403 blocked download for %s: %s", url, exc)
                return UdemyDownloadResult(drm_blocked=True, download_result=None)
            raise

        dr = self._make_result(info, url)
        logger.info("Downloaded Udemy lecture: %s", dr.title)
        return UdemyDownloadResult(drm_blocked=False, download_result=dr)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_ydl_params(self, url: str) -> dict:
        """Map UdemyDownloaderConfig to a yt-dlp params dict."""
        return {
            "format": self.config.format,
            "outtmpl": os.path.join(self.config.output_dir, "%(title)s [%(id)s].%(ext)s"),
            # Browser cookies let yt-dlp authenticate as the logged-in user.
            # yt-dlp expects a tuple: (browser, profile, keyring, container).
            "cookiesfrombrowser": (self.config.browser, None, None, None),
            # Udemy enforces Referer checks on its CDN.
            "referer": url,
            "writesubtitles": True,
            "subtitleslangs": self.config.subtitle_langs,
            "subtitlesformat": self.config.subtitle_format,
            "noplaylist": False,
            "ignoreerrors": False,  # we want to catch errors ourselves
            "quiet": self.config.quiet,
            "no_warnings": self.config.no_warnings,
        }

    def _is_drm_error(self, exc: Exception) -> bool:
        """Return True when *exc* looks like a DRM / HTTP 403 failure."""
        msg = str(exc).lower()
        return any(marker in msg for marker in _DRM_MARKERS)

    def _make_result(self, entry_info: dict, url: str) -> DownloadResult:
        """Build a DownloadResult from a yt-dlp entry info dict."""
        video_id = entry_info.get("id", "")
        title = entry_info.get("title", "")
        ext = entry_info.get("ext", "mp4")
        webpage_url = entry_info.get("webpage_url") or url

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

        lang: str | None = None
        for candidate in self.config.subtitle_langs:
            if candidate in requested:
                lang = candidate
                break

        if lang is None:
            return None, False, True

        sub_info = requested[lang]
        filepath = sub_info.get("filepath")

        if not filepath or not os.path.exists(filepath):
            return None, False, True

        creator_langs: set[str] = set(entry_info.get("subtitles") or {})
        subtitle_fallback = lang not in creator_langs

        return filepath, subtitle_fallback, False


def load_udemy_downloader_from_config(
    config_path: str = "config/config.yaml",
    output_dir: str | None = None,
) -> UdemyDownloader:
    """Create a UdemyDownloader from a YAML config file.

    Args:
        config_path: Path to the YAML config file.
        output_dir: Override for the output directory. If None, reads from config.

    Returns:
        Configured UdemyDownloader instance.
    """
    from src.config_loader import load_config

    cfg = load_config(config_path)

    dl_config = UdemyDownloaderConfig(
        output_dir=output_dir or cfg.get("udemy.output_dir", default="output/udemy"),
        browser=cfg.get("udemy.browser", default="chrome"),
        format=cfg.get(
            "udemy.format",
            default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        ),
        subtitle_langs=cfg.get("udemy.subtitle_langs", default=["en"]),
        subtitle_format=cfg.get("udemy.subtitle_format", default="srt"),
        quiet=cfg.get("udemy.quiet", default=True),
        no_warnings=cfg.get("udemy.no_warnings", default=True),
    )
    return UdemyDownloader(config=dl_config)
