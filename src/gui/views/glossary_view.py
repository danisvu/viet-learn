"""Glossary tab — CRUD terms, pack filter, import/export JSON."""
from __future__ import annotations

import json
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
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
from src.gui.views._glossary_dialog import GlossaryDialog
from src.models import GlossaryMode, GlossaryTerm

log = logging.getLogger(__name__)

_COLUMNS = ["English Term", "Vietnamese", "Mode", "Pack"]
_COL_EN, _COL_VI, _COL_MODE, _COL_PACK = range(4)
_PACKS_FILTER = ["All", "AI/ML", "Programming", "Math", "Custom"]
_READONLY = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class GlossaryView(BaseView):
    """View for managing the translation glossary."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Glossary",
            subtitle="Manage technical terms for consistent translation",
            parent=parent,
        )
        self._terms: list[GlossaryTerm] = []
        content = self.content_area()

        # ── Toolbar ───────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search terms…")
        self.search_input.setObjectName("url-input")
        toolbar.addWidget(self.search_input, stretch=1)

        self.pack_filter = QComboBox()
        self.pack_filter.addItems(_PACKS_FILTER)
        self.pack_filter.setFixedWidth(130)
        toolbar.addWidget(self.pack_filter)

        self.add_btn = QPushButton("+ Add Term")
        self.add_btn.setObjectName("primary-btn")
        self.add_btn.setFixedWidth(110)
        toolbar.addWidget(self.add_btn)

        content.addLayout(toolbar)
        content.addSpacing(10)

        # ── Table ─────────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setObjectName("glossary-table")
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(_COL_EN,   QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_VI,   QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(_COL_MODE, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(_COL_PACK, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        content.addWidget(self.table, stretch=1)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.count_label = QLabel("0 terms")
        self.count_label.setObjectName("status-label")
        action_row.addWidget(self.count_label)

        action_row.addStretch()

        self.import_btn = QPushButton("Import JSON")
        self.import_btn.setObjectName("secondary-btn")
        action_row.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export JSON")
        self.export_btn.setObjectName("secondary-btn")
        action_row.addWidget(self.export_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("secondary-btn")
        self.edit_btn.setEnabled(False)
        action_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger-btn")
        self.delete_btn.setEnabled(False)
        action_row.addWidget(self.delete_btn)

        content.addLayout(action_row)

        # ── Signal wiring ─────────────────────────────────────────────
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        self.search_input.textChanged.connect(self._apply_filter)
        self.pack_filter.currentTextChanged.connect(self._apply_filter)
        self.import_btn.clicked.connect(self._on_import)
        self.export_btn.clicked.connect(self._on_export)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_terms(self, terms: list[GlossaryTerm]) -> None:
        """Replace all terms and refresh the table."""
        self._terms = list(terms)
        self._rebuild_table()

    def get_terms(self) -> list[GlossaryTerm]:
        """Return all terms (unfiltered)."""
        return list(self._terms)

    def term_count(self) -> int:
        """Return total number of stored terms."""
        return len(self._terms)

    def do_import_json(self, path: str) -> int:
        """Load terms from *path* (JSON array). Returns count added."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        added = 0
        for item in data:
            try:
                term = GlossaryTerm(
                    english=item["english"],
                    vietnamese=item.get("vietnamese", ""),
                    mode=GlossaryMode(item.get("mode", GlossaryMode.REPLACE.value)),
                    pack=item.get("pack", "Custom"),
                )
                self._terms.append(term)
                added += 1
            except (KeyError, ValueError) as exc:
                log.warning("Skipping invalid term entry: %s", exc)
        self._rebuild_table()
        return added

    def do_export_json(self, path: str) -> None:
        """Write all terms to *path* as a JSON array."""
        data = [
            {
                "english": t.english,
                "vietnamese": t.vietnamese,
                "mode": t.mode.value,
                "pack": t.pack,
            }
            for t in self._terms
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        has_sel = bool(self.table.selectedItems())
        self.edit_btn.setEnabled(has_sel)
        self.delete_btn.setEnabled(has_sel)

    def _on_add(self) -> None:
        dlg = GlossaryDialog(parent=self)
        if dlg.exec() == GlossaryDialog.DialogCode.Accepted:
            self._terms.append(dlg.get_term())
            self._rebuild_table()

    def _on_edit(self) -> None:
        row = self._selected_term_index()
        if row is None:
            return
        dlg = GlossaryDialog(parent=self, term=self._terms[row])
        if dlg.exec() == GlossaryDialog.DialogCode.Accepted:
            self._terms[row] = dlg.get_term()
            self._rebuild_table()

    def _on_delete(self) -> None:
        rows = self._selected_term_indices()
        for idx in sorted(rows, reverse=True):
            del self._terms[idx]
        self._rebuild_table()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Glossary", "", "JSON Files (*.json)"
        )
        if path:
            try:
                self.do_import_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                log.error("Import failed: %s", exc)

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Glossary", "glossary.json", "JSON Files (*.json)"
        )
        if path:
            try:
                self.do_export_json(path)
            except OSError as exc:
                log.error("Export failed: %s", exc)

    def _apply_filter(self) -> None:
        needle = self.search_input.text().lower()
        pack_sel = self.pack_filter.currentText()
        visible = 0
        for row in range(self.table.rowCount()):
            en = self.table.item(row, _COL_EN)
            vi = self.table.item(row, _COL_VI)
            pk = self.table.item(row, _COL_PACK)
            text_match = (
                not needle
                or (en and needle in en.text().lower())
                or (vi and needle in vi.text().lower())
            )
            pack_match = pack_sel == "All" or (pk and pk.text() == pack_sel)
            show = text_match and pack_match
            self.table.setRowHidden(row, not show)
            if show:
                visible += 1
        total = len(self._terms)
        if needle or pack_sel != "All":
            self.count_label.setText(f"{visible}/{total} terms")
        else:
            self.count_label.setText(f"{total} terms")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _rebuild_table(self) -> None:
        self.table.setRowCount(0)
        for term in self._terms:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in [
                (_COL_EN,   term.english),
                (_COL_VI,   term.vietnamese),
                (_COL_MODE, term.mode.value),
                (_COL_PACK, term.pack),
            ]:
                item = QTableWidgetItem(text)
                item.setFlags(_READONLY)
                self.table.setItem(row, col, item)
        self._apply_filter()

    def _selected_term_index(self) -> int | None:
        """Return the _terms index of the first selected visible row."""
        rows = self._selected_term_indices()
        return rows[0] if rows else None

    def _selected_term_indices(self) -> list[int]:
        """Return _terms indices for all selected rows."""
        seen: set[int] = set()
        result: list[int] = []
        for idx in self.table.selectedIndexes():
            r = idx.row()
            if r not in seen:
                seen.add(r)
                # Map visible table row → _terms index (same order, no hidden)
                # Each table row corresponds to self._terms[row] directly
                result.append(r)
        return result
