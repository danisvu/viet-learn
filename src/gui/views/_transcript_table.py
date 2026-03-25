"""Bilingual subtitle table with inline editing and per-row audio preview."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from src.models import BilingualEntry

_COLUMNS = ["#", "Start", "End", "English", "Vietnamese", "▶"]
_COL_IDX, _COL_START, _COL_END, _COL_EN, _COL_VI, _COL_PLAY = range(6)
_READONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_EDITABLE = _READONLY | Qt.ItemFlag.ItemIsEditable
_AUDIO_ROLE = Qt.ItemDataRole.UserRole  # stored on index cell


class TranscriptTable(QTableWidget):
    """Side-by-side EN/VI table with inline edit and per-row play button.

    Signals:
        play_requested(row, audio_path): user clicked ▶ for *row*.
        entry_edited(row, new_en, new_vi): user finished editing a cell.
    """

    play_requested = pyqtSignal(int, str)
    entry_edited = pyqtSignal(int, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setObjectName("transcript-table")
        self.setHorizontalHeaderLabels(_COLUMNS)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(_COL_IDX,   QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_START, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_END,   QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_EN,    QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_VI,    QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_PLAY,  QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(_COL_PLAY, 36)

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)

        self._loading = False
        self.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_entries(self, entries: list[BilingualEntry]) -> None:
        """Replace table contents with *entries*."""
        self._loading = True
        self.setRowCount(0)
        for entry in entries:
            self._append_entry(entry)
        self.resizeRowsToContents()
        self._loading = False

    def get_all_entries(self) -> list[BilingualEntry]:
        """Return all entries, reflecting any inline edits."""
        return [self._entry_from_row(r) for r in range(self.rowCount())]

    def get_entry(self, row: int) -> BilingualEntry:
        """Return the entry at *row*."""
        return self._entry_from_row(row)

    def clear_entries(self) -> None:
        """Remove all rows."""
        self.setRowCount(0)

    def filter_rows(self, text: str) -> None:
        """Show only rows whose EN or VI text contains *text* (case-insensitive)."""
        needle = text.lower()
        for row in range(self.rowCount()):
            en = self.item(row, _COL_EN)
            vi = self.item(row, _COL_VI)
            match = (
                not needle
                or (en and needle in en.text().lower())
                or (vi and needle in vi.text().lower())
            )
            self.setRowHidden(row, not match)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _append_entry(self, entry: BilingualEntry) -> None:
        row = self.rowCount()
        self.insertRow(row)

        # Index cell — stores audio_path in UserRole
        idx_item = QTableWidgetItem(str(entry.index))
        idx_item.setFlags(_READONLY)
        idx_item.setData(_AUDIO_ROLE, entry.audio_path)
        self.setItem(row, _COL_IDX, idx_item)

        for col, (text, flags) in [
            (_COL_START, (entry.start,   _READONLY)),
            (_COL_END,   (entry.end,     _READONLY)),
            (_COL_EN,    (entry.text_en, _EDITABLE)),
            (_COL_VI,    (entry.text_vi, _EDITABLE)),
        ]:
            item = QTableWidgetItem(text)
            item.setFlags(flags)
            self.setItem(row, col, item)

        # Play button
        btn = QPushButton("▶")
        btn.setFixedSize(30, 24)
        btn.setToolTip("Preview audio")
        btn.setEnabled(bool(entry.audio_path))
        audio = entry.audio_path or ""
        btn.clicked.connect(lambda _c, r=row, a=audio: self.play_requested.emit(r, a))
        self.setCellWidget(row, _COL_PLAY, btn)

    def _entry_from_row(self, row: int) -> BilingualEntry:
        def txt(col: int) -> str:
            item = self.item(row, col)
            return item.text() if item else ""

        idx_item = self.item(row, _COL_IDX)
        audio_path = idx_item.data(_AUDIO_ROLE) if idx_item else None
        return BilingualEntry(
            index=int(txt(_COL_IDX) or 0),
            start=txt(_COL_START),
            end=txt(_COL_END),
            text_en=txt(_COL_EN),
            text_vi=txt(_COL_VI),
            audio_path=audio_path,
        )

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading or item.column() not in (_COL_EN, _COL_VI):
            return
        row = item.row()
        en = self.item(row, _COL_EN)
        vi = self.item(row, _COL_VI)
        self.entry_edited.emit(
            row,
            en.text() if en else "",
            vi.text() if vi else "",
        )
