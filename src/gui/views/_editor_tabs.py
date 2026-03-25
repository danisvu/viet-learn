"""Bottom tab panels for the transcript editor: Summary, Flashcards, PDF Notes."""
from __future__ import annotations

import csv
import io

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class SummaryTab(QWidget):
    """Editable plain-text summary pane."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("summary-edit")
        self.text_edit.setPlaceholderText("AI-generated summary will appear here…")
        layout.addWidget(self.text_edit, stretch=1)

        self._count_label = QLabel("")
        self._count_label.setObjectName("status-label")
        layout.addWidget(self._count_label)

        self.text_edit.textChanged.connect(self._update_count)

    def set_summary(self, text: str) -> None:
        """Replace summary content."""
        self.text_edit.setPlainText(text)

    def get_summary(self) -> str:
        """Return current summary text."""
        return self.text_edit.toPlainText()

    def _update_count(self) -> None:
        text = self.text_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        self._count_label.setText(f"{words} words · {len(text)} chars")


class FlashcardsTab(QWidget):
    """Two-column card list: English Term | Vietnamese Definition."""

    _COLUMNS = ["English Term", "Vietnamese Definition"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.add_btn = QPushButton("+ Add Card")
        self.add_btn.setObjectName("primary-btn")
        self.add_btn.setFixedWidth(100)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger-btn")
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)
        layout.addLayout(toolbar)

        # Card table
        self.table = QTableWidget(0, 2)
        self.table.setObjectName("flashcard-table")
        self.table.setHorizontalHeaderLabels(self._COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        self.add_btn.clicked.connect(self._add_empty_card)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def add_card(self, term: str, definition: str) -> None:
        """Append a card with preset content."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(term))
        self.table.setItem(row, 1, QTableWidgetItem(definition))

    def card_count(self) -> int:
        return self.table.rowCount()

    def get_cards(self) -> list[tuple[str, str]]:
        """Return all cards as (term, definition) tuples."""
        cards = []
        for row in range(self.table.rowCount()):
            t = self.table.item(row, 0)
            d = self.table.item(row, 1)
            cards.append((t.text() if t else "", d.text() if d else ""))
        return cards

    def clear_cards(self) -> None:
        self.table.setRowCount(0)

    def _add_empty_card(self) -> None:
        self.add_card("", "")
        row = self.table.rowCount() - 1
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def _delete_selected(self) -> None:
        rows = sorted(
            {idx.row() for idx in self.table.selectedIndexes()}, reverse=True
        )
        for row in rows:
            self.table.removeRow(row)

    def _on_selection_changed(self) -> None:
        self.delete_btn.setEnabled(bool(self.table.selectedItems()))


class PdfNotesTab(QWidget):
    """Freeform notes pane with plain-text export (PDF if reportlab available)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(4)

        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("notes-edit")
        self.text_edit.setPlaceholderText("Add study notes here…")
        layout.addWidget(self.text_edit, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.export_btn = QPushButton("Export Notes")
        self.export_btn.setObjectName("secondary-btn")
        btn_row.addWidget(self.export_btn)
        layout.addLayout(btn_row)

    def set_notes(self, text: str) -> None:
        self.text_edit.setPlainText(text)

    def get_notes(self) -> str:
        return self.text_edit.toPlainText()
