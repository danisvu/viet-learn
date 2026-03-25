"""YouTube tab — URL input, playlist detection, batch download queue."""
from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._badge import detect_url_type
from src.gui.views._base import BaseView
from src.gui.views._download_panel import ActiveDownloadPanel, SubtitlePreviewPanel
from src.gui.views._worker import ItemStatus, QueueEntry, _DownloadWorker

log = logging.getLogger(__name__)

_COLUMNS = ["Title / URL", "Type", "Status", "Progress"]
_COL_URL, _COL_TYPE, _COL_STATUS, _COL_PROGRESS = range(4)
_URL_DATA = Qt.ItemDataRole.UserRole  # stores original URL in the URL cell


class YouTubeView(BaseView):
    """View for downloading YouTube videos and playlists."""

    def __init__(
        self,
        downloader_factory: Callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title="YouTube",
            subtitle="Download videos and playlists with auto-subtitles",
            parent=parent,
        )
        self._downloader_factory = downloader_factory
        self._entries: dict[str, QueueEntry] = {}
        self._worker: _DownloadWorker | None = None

        content = self.content_area()

        # ── URL input row ─────────────────────────────────────────────
        url_row = QHBoxLayout()
        url_row.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube URL or playlist URL…")
        self.url_input.setObjectName("url-input")
        url_row.addWidget(self.url_input, stretch=1)

        self._badge_label = QLabel("")
        self._badge_label.setObjectName("status-label")
        self._badge_label.setFixedWidth(70)
        url_row.addWidget(self._badge_label)

        self.add_btn = QPushButton("Add to Queue")
        self.add_btn.setObjectName("primary-btn")
        self.add_btn.setFixedWidth(130)
        url_row.addWidget(self.add_btn)

        content.addLayout(url_row)
        content.addSpacing(10)

        # ── Queue table ───────────────────────────────────────────────
        queue_label = QLabel("Download Queue")
        queue_label.setObjectName("section-label")
        content.addWidget(queue_label)
        content.addSpacing(6)

        self.queue_table = QTableWidget(0, len(_COLUMNS))
        self.queue_table.setObjectName("queue-table")
        self.queue_table.setHorizontalHeaderLabels(_COLUMNS)
        hh = self.queue_table.horizontalHeader()
        hh.setSectionResizeMode(_COL_URL, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_TYPE, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_PROGRESS, QHeaderView.ResizeMode.ResizeToContents)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setAlternatingRowColors(True)
        content.addWidget(self.queue_table, stretch=1)

        # ── Active download panel (hidden until download starts) ──────
        self._active_panel = ActiveDownloadPanel()
        self._active_panel.hide()
        content.addWidget(self._active_panel)

        # ── Subtitle preview (hidden until subtitle data arrives) ─────
        self._subtitle_panel = SubtitlePreviewPanel()
        self._subtitle_panel.hide()
        content.addWidget(self._subtitle_panel)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._count_label = QLabel("0 items")
        self._count_label.setObjectName("status-label")
        action_row.addWidget(self._count_label)
        action_row.addStretch()

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.setObjectName("secondary-btn")
        self.remove_btn.setEnabled(False)
        action_row.addWidget(self.remove_btn)

        self.clear_done_btn = QPushButton("Clear Done")
        self.clear_done_btn.setObjectName("secondary-btn")
        action_row.addWidget(self.clear_done_btn)

        self.download_btn = QPushButton("Download All")
        self.download_btn.setObjectName("primary-btn")
        self.download_btn.setFixedWidth(130)
        action_row.addWidget(self.download_btn)
        content.addLayout(action_row)

        # ── Signal wiring ─────────────────────────────────────────────
        self.url_input.textChanged.connect(self._on_url_changed)
        self.url_input.returnPressed.connect(self._add_url)
        self.add_btn.clicked.connect(self._add_url)
        self.download_btn.clicked.connect(self._start_download)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_done_btn.clicked.connect(self._clear_done)
        self.queue_table.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def queue_size(self) -> int:
        """Return number of entries currently in the queue."""
        return len(self._entries)

    def entry(self, url: str) -> QueueEntry | None:
        """Return the QueueEntry for *url*, or None."""
        return self._entries.get(url)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_url_changed(self, text: str) -> None:
        self._badge_label.setText(detect_url_type(text)[0])

    def _add_url(self) -> None:
        url = self.url_input.text().strip()
        if not url or url in self._entries:
            return
        badge, is_playlist = detect_url_type(url)
        entry = QueueEntry(url=url, badge=badge, is_playlist=is_playlist)
        self._entries[url] = entry
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        url_item = QTableWidgetItem(url)
        url_item.setData(_URL_DATA, url)  # preserve original URL even after title update
        self.queue_table.setItem(row, _COL_URL, url_item)
        self.queue_table.setItem(row, _COL_TYPE, QTableWidgetItem(badge))
        self.queue_table.setItem(row, _COL_STATUS, QTableWidgetItem(ItemStatus.PENDING.label()))
        self.queue_table.setItem(row, _COL_PROGRESS, QTableWidgetItem(""))
        self.url_input.clear()
        self._update_counts()

    def _row_for_url(self, url: str) -> int | None:
        for r in range(self.queue_table.rowCount()):
            item = self.queue_table.item(r, _COL_URL)
            if item and item.data(_URL_DATA) == url:
                return r
        return None

    def _set_row_status(self, url: str, status: ItemStatus, progress: str = "") -> None:
        entry = self._entries.get(url)
        if entry is None:
            return
        entry.status = status
        entry.progress = progress
        row = self._row_for_url(url)
        if row is None:
            return
        self.queue_table.item(row, _COL_STATUS).setText(status.label())
        self.queue_table.item(row, _COL_PROGRESS).setText(progress)

    def _start_download(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._downloader_factory is None:
            return
        pending = [url for url, e in self._entries.items() if e.status == ItemStatus.PENDING]
        if not pending:
            return
        self.download_btn.setEnabled(False)
        self._active_panel.reset()
        self._active_panel.show()
        self._worker = _DownloadWorker(pending, self._downloader_factory, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.item_error.connect(self._on_item_error)
        self._worker.step_changed.connect(self._on_step_changed)
        self._worker.byte_progress.connect(self._on_byte_progress)
        self._worker.subtitle_preview.connect(self._on_subtitle_preview)
        self._worker.finished.connect(self._on_worker_finished)
        for url in pending:
            self._set_row_status(url, ItemStatus.DOWNLOADING)
        self._worker.start()

    def _on_progress(self, url: str, current: int, total: int, title: str) -> None:
        entry = self._entries.get(url)
        if entry:
            entry.title = title
        progress = f"{current}/{total}" if total else str(current)
        self._set_row_status(url, ItemStatus.DOWNLOADING, progress)
        row = self._row_for_url(url)
        if row is not None and title:
            self.queue_table.item(row, _COL_URL).setText(title)

    def _on_item_done(self, url: str, results: list) -> None:
        self._set_row_status(url, ItemStatus.DONE, f"{len(results)} file(s)")
        self._update_counts()

    def _on_item_error(self, url: str, error: str) -> None:
        self._set_row_status(url, ItemStatus.ERROR, error[:40])
        self._update_counts()

    def _on_worker_finished(self) -> None:
        self.download_btn.setEnabled(True)
        self._active_panel.set_complete()

    def _on_step_changed(self, url: str, step: str) -> None:
        self._active_panel.update_step(step)

    def _on_byte_progress(
        self, url: str, downloaded: int, total: int, eta_secs: int, speed: float
    ) -> None:
        self._active_panel.update_byte_progress(downloaded, total, eta_secs, speed)

    def _on_subtitle_preview(self, url: str, text: str) -> None:
        self._subtitle_panel.show_preview(text)
        self._subtitle_panel.show()

    def _remove_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self.queue_table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            item = self.queue_table.item(row, _COL_URL)
            if item:
                url = item.data(_URL_DATA) or item.text()
                self._entries.pop(url, None)
            self.queue_table.removeRow(row)
        self._update_counts()

    def _clear_done(self) -> None:
        for url in [u for u, e in self._entries.items() if e.status == ItemStatus.DONE]:
            row = self._row_for_url(url)
            if row is not None:
                self.queue_table.removeRow(row)
            del self._entries[url]
        self._update_counts()

    def _on_selection_changed(self) -> None:
        self.remove_btn.setEnabled(bool(self.queue_table.selectedItems()))

    def _update_counts(self) -> None:
        total = len(self._entries)
        done = sum(1 for e in self._entries.values() if e.status == ItemStatus.DONE)
        suffix = f" ({done} done)" if done else ""
        self._count_label.setText(f"{total} item{'s' if total != 1 else ''}{suffix}")
