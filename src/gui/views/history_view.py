"""History tab — browse and search processed videos."""
from __future__ import annotations

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

from src.gui.views._base import BaseView

_COLUMNS = ["Title", "Platform", "Date", "Duration", "Status"]


class HistoryView(BaseView):
    """View for browsing all processed video history."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="History",
            subtitle="All processed videos — click a row to review",
            parent=parent,
        )

        content = self.content_area()

        # ── Search row ────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, platform, date…")
        self.search_input.setObjectName("url-input")
        search_row.addWidget(self.search_input, stretch=1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("secondary-btn")
        self.search_btn.setFixedWidth(90)
        search_row.addWidget(self.search_btn)

        content.addLayout(search_row)
        content.addSpacing(10)

        # ── History table ─────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("history-table")
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        content.addWidget(self.table, stretch=1)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()

        self.count_label = QLabel("0 videos")
        self.count_label.setObjectName("status-label")
        action_row.addWidget(self.count_label)

        action_row.addStretch()

        self.open_btn = QPushButton("Open Selected")
        self.open_btn.setObjectName("secondary-btn")
        self.open_btn.setEnabled(False)
        action_row.addWidget(self.open_btn)

        content.addLayout(action_row)

        # Wire selection → enable open button
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        self.open_btn.setEnabled(bool(self.table.selectedItems()))
