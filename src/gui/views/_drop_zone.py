"""Reusable drag-and-drop zone widget for video + subtitle file import."""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

log = logging.getLogger(__name__)

_VIDEO_EXTS: frozenset[str] = frozenset({".mp4", ".webm", ".mkv"})
_SUBTITLE_EXTS: frozenset[str] = frozenset({".srt", ".vtt"})
_ACCEPTED_EXTS: frozenset[str] = _VIDEO_EXTS | _SUBTITLE_EXTS

_STYLE_IDLE = """
FileDropZone {
    background-color: #1e1e2e;
    border: 2px dashed #45475a;
    border-radius: 10px;
}
"""
_STYLE_HOVER = """
FileDropZone {
    background-color: #313244;
    border: 2px dashed #89b4fa;
    border-radius: 10px;
}
"""
_STYLE_ERROR = """
FileDropZone {
    background-color: #1e1e2e;
    border: 2px dashed #f38ba8;
    border-radius: 10px;
}
"""


def validate_drop_paths(paths: list[str]) -> tuple[list[str], list[str], str]:
    """Classify *paths* and validate the proposed drop.

    Returns:
        A ``(videos, subtitles, error)`` tuple.  *error* is an empty string
        when the drop is valid; otherwise it contains a human-readable message
        and both lists are empty.
    """
    videos = [p for p in paths if Path(p).suffix.lower() in _VIDEO_EXTS]
    subtitles = [p for p in paths if Path(p).suffix.lower() in _SUBTITLE_EXTS]
    unknown = [p for p in paths if Path(p).suffix.lower() not in _ACCEPTED_EXTS]

    if len(videos) > 1:
        return [], [], "Drop only one video file at a time."
    if len(subtitles) > 1:
        return [], [], "Drop only one subtitle file at a time."
    if unknown:
        exts = ", ".join(Path(p).suffix or "(no ext)" for p in unknown)
        return [], [], f"Unsupported file type: {exts}"

    return videos, subtitles, ""


class FileDropZone(QWidget):
    """Drop zone that accepts video and/or subtitle files.

    Supports dropping one video file (*.mp4, *.webm, *.mkv) and one subtitle
    file (*.srt, *.vtt) at a time — either individually or together.

    Signals:
        video_dropped(str): Absolute path of the accepted video file.
        subtitle_dropped(str): Absolute path of the accepted subtitle file.
        error(str): Human-readable validation error message.
    """

    video_dropped = pyqtSignal(str)
    subtitle_dropped = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self.setStyleSheet(_STYLE_IDLE)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._icon_label = QLabel("\u2B07")   # ⬇
        self._icon_label.setObjectName("drop-icon")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet(
            "font-size: 26px; color: #45475a; background: transparent;"
        )
        layout.addWidget(self._icon_label)

        self._hint_label = QLabel("Drop video + subtitle here")
        self._hint_label.setObjectName("drop-hint")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(
            "font-size: 13px; color: #6c7086; background: transparent;"
        )
        layout.addWidget(self._hint_label)

        types_label = QLabel("Video: .mp4 .webm .mkv  \u00b7  Subtitle: .srt .vtt")
        types_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        types_label.setStyleSheet(
            "font-size: 11px; color: #45475a; background: transparent;"
        )
        layout.addWidget(types_label)

    # ------------------------------------------------------------------
    # Qt drag/drop overrides
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls()]
            if any(Path(p).suffix.lower() in _ACCEPTED_EXTS for p in paths):
                event.acceptProposedAction()
                self.setStyleSheet(_STYLE_HOVER)
                self._hint_label.setStyleSheet(
                    "font-size: 13px; color: #89b4fa; background: transparent;"
                )
                return
        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: ARG002
        self._reset_style()

    def dropEvent(self, event: QDropEvent) -> None:
        self._reset_style()
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        videos, subtitles, err = validate_drop_paths(paths)
        if err:
            self._show_error(err)
            return
        for path in videos:
            log.debug("Video dropped: %s", path)
            self.video_dropped.emit(path)
        for path in subtitles:
            log.debug("Subtitle dropped: %s", path)
            self.subtitle_dropped.emit(path)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def classify_file(path: str) -> str:
        """Return ``"video"``, ``"subtitle"``, or ``""`` for *path*."""
        ext = Path(path).suffix.lower()
        if ext in _VIDEO_EXTS:
            return "video"
        if ext in _SUBTITLE_EXTS:
            return "subtitle"
        return ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset_style(self) -> None:
        self.setStyleSheet(_STYLE_IDLE)
        self._hint_label.setStyleSheet(
            "font-size: 13px; color: #6c7086; background: transparent;"
        )

    def _show_error(self, message: str) -> None:
        log.warning("Drop zone validation error: %s", message)
        self.setStyleSheet(_STYLE_ERROR)
        self._hint_label.setStyleSheet(
            "font-size: 13px; color: #f38ba8; background: transparent;"
        )
        self.error.emit(message)
