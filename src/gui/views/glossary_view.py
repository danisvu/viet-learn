"""Glossary tab — manage technical term packs and custom entries."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView

_COLUMNS = ["English Term", "Vietnamese", "Mode"]


class GlossaryView(BaseView):
    """View for managing the translation glossary."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Glossary",
            subtitle="Manage technical terms for consistent translation",
            parent=parent,
        )

        content = self.content_area()

        # ── Toolbar row ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search terms…")
        self.search_input.setObjectName("url-input")
        toolbar.addWidget(self.search_input, stretch=1)

        self.add_btn = QPushButton("+ Add Term")
        self.add_btn.setObjectName("primary-btn")
        self.add_btn.setFixedWidth(110)
        toolbar.addWidget(self.add_btn)

        content.addLayout(toolbar)
        content.addSpacing(10)

        # ── Glossary table ────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("glossary-table")
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.verticalHeader().setVisible(False)
        content.addWidget(self.table, stretch=1)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()

        self.count_label = QLabel("0 terms")
        self.count_label.setObjectName("status-label")
        action_row.addWidget(self.count_label)

        action_row.addStretch()

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("secondary-btn")
        self.edit_btn.setEnabled(False)
        action_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger-btn")
        self.delete_btn.setEnabled(False)
        action_row.addWidget(self.delete_btn)

        content.addLayout(action_row)

        # Wire selection → enable edit/delete
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        has_sel = bool(self.table.selectedItems())
        self.edit_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)
