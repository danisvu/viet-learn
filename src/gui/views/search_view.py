"""Transcript search view — FTS5 search with platform / date / topic filters."""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView
from src.models import SearchResult
from src.transcript_db import TranscriptDB, _ms_to_timestamp

logger = logging.getLogger(__name__)

_PLATFORMS = ["All", "youtube", "dlai", "udemy", "capture", "other"]

_TABLE_HEADERS = ["Title", "Platform", "Date", "Topic", "Snippet", "Timestamp"]

_EXTRA_STYLE = """
QLineEdit#search-input {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit#search-input:focus {
    border-color: #89b4fa;
}
QDateEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}
QTableWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 6px;
    font-size: 12px;
}
QTableWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}
QLabel#result-count {
    color: #6c7086;
    font-size: 11px;
    background: transparent;
}
"""


class SearchView(BaseView):
    """Full-text search across all stored transcripts.

    Signals
    -------
    result_activated(SearchResult)
        Emitted when the user double-clicks a result row. Carries the full
        :class:`~src.models.SearchResult` so callers can open the transcript
        and jump to the timestamp.
    """

    result_activated = pyqtSignal(object)  # SearchResult

    def __init__(
        self,
        db: TranscriptDB | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            "Transcript Search",
            "Full-text search across all transcripts. Double-click a result to jump to that timestamp.",
            parent,
        )
        self.setStyleSheet(self.styleSheet() + _EXTRA_STYLE)

        # Use supplied db or open the default one
        if db is not None:
            self._db = db
            self._owns_db = False
        else:
            default_path = Path.home() / ".viet-learn" / "transcripts.db"
            self._db = TranscriptDB(default_path)
            self._owns_db = True

        self._results: list[SearchResult] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        ca = self.content_area()

        # ── Filter row ────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search-input")
        self._search_input.setPlaceholderText("Search transcripts…")
        self._search_input.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._search_input.returnPressed.connect(self._do_search)
        filter_row.addWidget(self._search_input, stretch=3)

        self._platform_cb = QComboBox()
        self._platform_cb.addItems(_PLATFORMS)
        self._platform_cb.setFixedWidth(110)
        filter_row.addWidget(QLabel("Platform:"))
        filter_row.addWidget(self._platform_cb)

        filter_row.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setCalendarPopup(True)
        self._date_from.setSpecialValueText("—")
        self._date_from.setDate(QDate(2000, 1, 1))
        self._date_from.setFixedWidth(110)
        filter_row.addWidget(self._date_from)

        filter_row.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setCalendarPopup(True)
        self._date_to.setSpecialValueText("—")
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setFixedWidth(110)
        filter_row.addWidget(self._date_to)

        filter_row.addWidget(QLabel("Topic:"))
        self._topic_input = QLineEdit()
        self._topic_input.setPlaceholderText("any")
        self._topic_input.setFixedWidth(100)
        filter_row.addWidget(self._topic_input)

        search_btn = QPushButton("Search")
        search_btn.setObjectName("primary-btn")
        search_btn.setFixedWidth(80)
        search_btn.clicked.connect(self._do_search)
        filter_row.addWidget(search_btn)

        ca.addLayout(filter_row)

        # ── Results table ─────────────────────────────────────────────
        self._table = QTableWidget(0, len(_TABLE_HEADERS))
        self._table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setColumnWidth(0, 200)  # Title
        self._table.setColumnWidth(1, 80)   # Platform
        self._table.setColumnWidth(2, 90)   # Date
        self._table.setColumnWidth(3, 90)   # Topic
        self._table.setColumnWidth(4, 320)  # Snippet
        self._table.setColumnWidth(5, 80)   # Timestamp
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_double_click)
        ca.addWidget(self._table, stretch=1)

        # ── Status bar ────────────────────────────────────────────────
        self._count_label = QLabel("Enter a query to search.")
        self._count_label.setObjectName("result-count")
        ca.addWidget(self._count_label)

    # ------------------------------------------------------------------
    # Search logic
    # ------------------------------------------------------------------

    def _do_search(self) -> None:
        query = self._search_input.text().strip()
        if not query:
            self._count_label.setText("Enter a query to search.")
            self._table.setRowCount(0)
            return

        platform = self._platform_cb.currentText()
        platform_filter = None if platform == "All" else platform

        date_from = self._date_from.date().toString("yyyy-MM-dd")
        date_to = self._date_to.date().toString("yyyy-MM-dd")
        # Treat sentinel date (2000-01-01) as "no filter"
        date_from_filter = date_from if date_from != "2000-01-01" else None
        date_to_filter = date_to if date_to != QDate.currentDate().toString("yyyy-MM-dd") else None

        topic = self._topic_input.text().strip() or None

        try:
            results = self._db.search(
                query,
                platform=platform_filter,
                date_from=date_from_filter,
                date_to=date_to_filter,
                topic=topic,
            )
        except Exception as exc:
            logger.error("Search failed: %s", exc)
            self._count_label.setText(f"Search error: {exc}")
            return

        self._results = results
        self._populate_table(results)

    def _populate_table(self, results: list[SearchResult]) -> None:
        self._table.setRowCount(0)
        for r in results:
            row = self._table.rowCount()
            self._table.insertRow(row)

            cells = [
                r.title,
                r.platform,
                r.date_added,
                r.topic or "",
                r.snippet,
                _ms_to_timestamp(r.start_ms),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(f"{r.text_en}\n{r.text_vi}")
                self._table.setItem(row, col, item)

        count = len(results)
        self._count_label.setText(
            f"{count} result{'s' if count != 1 else ''} found."
            if count > 0
            else "No results found."
        )

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _on_double_click(self, index: object) -> None:
        row = self._table.currentRow()
        if 0 <= row < len(self._results):
            self.result_activated.emit(self._results[row])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_db(self, db: TranscriptDB) -> None:
        """Replace the database instance (e.g. after opening a different file)."""
        if self._owns_db:
            self._db.close()
        self._db = db
        self._owns_db = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self._owns_db:
            self._db.close()
        super().closeEvent(event)  # type: ignore[misc]
