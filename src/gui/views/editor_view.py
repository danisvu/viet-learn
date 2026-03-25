"""Transcript editor — bilingual table, inline edit, audio preview, export."""
from __future__ import annotations

import csv
import logging
import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView
from src.gui.views._editor_tabs import FlashcardsTab, PdfNotesTab, SummaryTab
from src.gui.views._transcript_table import TranscriptTable
from src.models import BilingualEntry

log = logging.getLogger(__name__)


class EditorView(BaseView):
    """Bilingual transcript editor with summary, flashcard, and notes tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Transcript Editor",
            subtitle="Review and edit bilingual subtitles, then export",
            parent=parent,
        )
        self._entries: list[BilingualEntry] = []
        content = self.content_area()

        # ── Toolbar row ───────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._file_label = QLabel("No file loaded")
        self._file_label.setObjectName("status-label")
        toolbar.addWidget(self._file_label, stretch=1)

        self.export_srt_btn = QPushButton("Export SRT")
        self.export_srt_btn.setObjectName("secondary-btn")
        toolbar.addWidget(self.export_srt_btn)

        self.export_txt_btn = QPushButton("Export TXT")
        self.export_txt_btn.setObjectName("secondary-btn")
        toolbar.addWidget(self.export_txt_btn)

        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.setObjectName("secondary-btn")
        toolbar.addWidget(self.export_csv_btn)

        content.addLayout(toolbar)
        content.addSpacing(6)

        # ── Search + filter row ───────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("url-input")
        self.search_input.setPlaceholderText("Search subtitles…")
        search_row.addWidget(self.search_input, stretch=1)

        self._match_label = QLabel("")
        self._match_label.setObjectName("status-label")
        search_row.addWidget(self._match_label)

        content.addLayout(search_row)
        content.addSpacing(6)

        # ── Transcript table ──────────────────────────────────────────
        self.transcript_table = TranscriptTable()
        content.addWidget(self.transcript_table, stretch=1)

        # ── Bottom tab widget ─────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setFixedHeight(220)
        self.tabs.setObjectName("editor-tabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #313244;
                background-color: #1e1e2e;
                border-radius: 0 0 6px 6px;
            }
            QTabBar::tab {
                background-color: #313244;
                color: #a6adc8;
                padding: 6px 16px;
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e2e;
                color: #89b4fa;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background-color: #45475a;
                color: #cdd6f4;
            }
        """)

        self.summary_tab = SummaryTab()
        self.flashcards_tab = FlashcardsTab()
        self.pdf_notes_tab = PdfNotesTab()

        self.tabs.addTab(self.summary_tab, "Summary")
        self.tabs.addTab(self.flashcards_tab, "Flashcards")
        self.tabs.addTab(self.pdf_notes_tab, "PDF Notes")

        content.addWidget(self.tabs)

        # ── Signal wiring ─────────────────────────────────────────────
        self.search_input.textChanged.connect(self._on_search)
        self.transcript_table.play_requested.connect(self._on_play_requested)
        self.transcript_table.entry_edited.connect(self._on_entry_edited)
        self.export_srt_btn.clicked.connect(self._export_srt)
        self.export_txt_btn.clicked.connect(self._export_txt)
        self.export_csv_btn.clicked.connect(self._export_csv)
        self.pdf_notes_tab.export_btn.clicked.connect(self._export_notes)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_entries(self, entries: list[BilingualEntry], title: str = "") -> None:
        """Load *entries* into the editor table."""
        self._entries = list(entries)
        self.transcript_table.load_entries(entries)
        self._file_label.setText(title or f"{len(entries)} entries")

    def get_entries(self) -> list[BilingualEntry]:
        """Return all entries reflecting current edits."""
        return self.transcript_table.get_all_entries()

    def row_count(self) -> int:
        return self.transcript_table.rowCount()

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_search(self, text: str) -> None:
        self.transcript_table.filter_rows(text)
        visible = sum(
            1 for r in range(self.transcript_table.rowCount())
            if not self.transcript_table.isRowHidden(r)
        )
        total = self.transcript_table.rowCount()
        self._match_label.setText(f"{visible}/{total}" if text else "")

    def _on_play_requested(self, row: int, audio_path: str) -> None:
        if not audio_path or not os.path.exists(audio_path):
            log.warning("Audio not found: %s", audio_path)
            return
        try:
            subprocess.Popen(["afplay", audio_path])
        except FileNotFoundError:
            # afplay not available (non-macOS); try aplay or paplay
            for player in ("aplay", "paplay", "ffplay"):
                try:
                    subprocess.Popen([player, audio_path])
                    break
                except FileNotFoundError:
                    continue

    def _on_entry_edited(self, row: int, new_en: str, new_vi: str) -> None:
        if row < len(self._entries):
            self._entries[row].text_en = new_en
            self._entries[row].text_vi = new_vi
            self._entries[row].edited = True

    def _export_srt(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export SRT", "subtitles_vi.srt", "SRT Files (*.srt)"
        )
        if path:
            self._do_export_srt(path)

    def _do_export_srt(self, path: str) -> None:
        """Write Vietnamese SRT to *path*."""
        entries = self.transcript_table.get_all_entries()
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(f"{e.index}\n{e.start} --> {e.end}\n{e.text_vi}\n\n")

    def _export_txt(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export TXT", "transcript.txt", "Text Files (*.txt)"
        )
        if path:
            self._do_export_txt(path)

    def _do_export_txt(self, path: str) -> None:
        """Write bilingual plain-text transcript to *path*."""
        entries = self.transcript_table.get_all_entries()
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(f"[{e.start} --> {e.end}]\n{e.text_en}\n{e.text_vi}\n\n")

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "transcript.csv", "CSV Files (*.csv)"
        )
        if path:
            self._do_export_csv(path)

    def _do_export_csv(self, path: str) -> None:
        """Write bilingual CSV to *path*."""
        entries = self.transcript_table.get_all_entries()
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["#", "Start", "End", "English", "Vietnamese"])
            for e in entries:
                writer.writerow([e.index, e.start, e.end, e.text_en, e.text_vi])

    def _export_notes(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Notes", "notes.txt", "Text Files (*.txt);;PDF Files (*.pdf)"
        )
        if not path:
            return
        notes = self.pdf_notes_tab.get_notes()
        with open(path, "w", encoding="utf-8") as f:
            f.write(notes)
