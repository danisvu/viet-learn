"""Background download worker thread, item status enum, and queue entry type."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)


class ItemStatus(Enum):
    """Download queue item status."""

    PENDING = auto()
    DOWNLOADING = auto()
    DONE = auto()
    ERROR = auto()

    def label(self) -> str:
        """Human-readable status string."""
        return {
            ItemStatus.PENDING: "Pending",
            ItemStatus.DOWNLOADING: "Downloading…",
            ItemStatus.DONE: "Done",
            ItemStatus.ERROR: "Error",
        }[self]


@dataclass
class QueueEntry:
    """Represents one URL in the download queue."""

    url: str
    badge: str          # "Video" | "Playlist" | ""
    is_playlist: bool
    status: ItemStatus = ItemStatus.PENDING
    progress: str = ""
    title: str = ""     # populated once download starts


class _DownloadWorker(QThread):
    """Background thread that downloads each queued URL via YouTubeDownloader."""

    # (url, current_item, total_items, title)
    progress = pyqtSignal(str, int, int, str)
    # (url, results_list)
    item_done = pyqtSignal(str, list)
    # (url, error_message)
    item_error = pyqtSignal(str, str)
    # (url, step_description)
    step_changed = pyqtSignal(str, str)
    # (url, srt_preview_text)
    subtitle_preview = pyqtSignal(str, str)
    # (url, downloaded_bytes, total_bytes, eta_secs, speed_bps)
    byte_progress = pyqtSignal(str, int, int, int, float)

    def __init__(
        self,
        urls: list[str],
        downloader_factory: Callable,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._urls = urls
        self._downloader_factory = downloader_factory

    def run(self) -> None:  # noqa: D102
        downloader = self._downloader_factory()
        n = len(self._urls)
        for i, url in enumerate(self._urls, start=1):
            try:
                self.step_changed.emit(url, f"{i}/{n} — Fetching info…")
                hook = self._make_hook(url)

                def _cb(cur: int, tot: int, title: str, u=url, ii=i, nn=n) -> None:
                    self.progress.emit(u, cur, tot, title)
                    self.step_changed.emit(u, f"{ii}/{nn} — Downloading ({cur}/{tot})")

                results = downloader.download(url, progress_callback=_cb, ytdlp_hooks=[hook])
                self.step_changed.emit(url, f"{i}/{n} — Complete ✓")

                # Emit subtitle preview for the first result that has subtitles
                for r in results:
                    if getattr(r, "subtitle_path", None):
                        preview = self._read_subtitle_preview(r.subtitle_path)
                        if preview:
                            self.subtitle_preview.emit(url, preview)
                        break

                self.item_done.emit(url, results)
            except Exception as exc:  # noqa: BLE001
                log.error("Download failed for %s: %s", url, exc)
                self.item_error.emit(url, str(exc))

    def _make_hook(self, url: str) -> Callable:
        """Return a yt-dlp progress hook that emits byte_progress and step_changed."""
        def hook(d: dict) -> None:
            status = d.get("status")
            if status == "downloading":
                downloaded = int(d.get("downloaded_bytes") or 0)
                total = int((d.get("total_bytes") or d.get("total_bytes_estimate")) or 0)
                eta = int(d.get("eta") or 0)
                speed = float(d.get("speed") or 0.0)
                self.byte_progress.emit(url, downloaded, total, eta, speed)
            elif status == "finished":
                self.step_changed.emit(url, "Merging…")
        return hook

    @staticmethod
    def _read_subtitle_preview(srt_path: str, max_entries: int = 3) -> str:
        """Return the first *max_entries* SRT blocks from *srt_path* as a string."""
        try:
            with open(srt_path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return ""
        blocks = [b.strip() for b in content.strip().split("\n\n") if b.strip()]
        return "\n\n".join(blocks[:max_entries])
