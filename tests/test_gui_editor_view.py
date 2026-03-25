"""Tests for EditorView, TranscriptTable, and editor tab widgets.

PyQt6 runs offscreen — no display required.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.models import BilingualEntry
from src.gui.views._transcript_table import TranscriptTable
from src.gui.views._editor_tabs import SummaryTab, FlashcardsTab, PdfNotesTab
from src.gui.views.editor_view import EditorView


# ── Shared QApplication ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Sample entries ────────────────────────────────────────────────────────────

def make_entries(n: int = 3) -> list[BilingualEntry]:
    return [
        BilingualEntry(
            index=i,
            start=f"00:00:0{i},000",
            end=f"00:00:0{i+1},000",
            text_en=f"English line {i}",
            text_vi=f"Vietnamese line {i}",
        )
        for i in range(1, n + 1)
    ]


# ---------------------------------------------------------------------------
# TestBilingualEntry
# ---------------------------------------------------------------------------

class TestBilingualEntry:
    def test_required_fields(self):
        e = BilingualEntry(
            index=1, start="00:00:01,000", end="00:00:02,000",
            text_en="Hello", text_vi="Xin chào",
        )
        assert e.index == 1
        assert e.text_en == "Hello"
        assert e.text_vi == "Xin chào"

    def test_audio_path_defaults_none(self):
        e = BilingualEntry(index=1, start="", end="", text_en="", text_vi="")
        assert e.audio_path is None

    def test_edited_defaults_false(self):
        e = BilingualEntry(index=1, start="", end="", text_en="", text_vi="")
        assert e.edited is False

    def test_with_audio_path(self):
        e = BilingualEntry(
            index=1, start="", end="", text_en="", text_vi="",
            audio_path="/tmp/line1.wav",
        )
        assert e.audio_path == "/tmp/line1.wav"


# ---------------------------------------------------------------------------
# TestTranscriptTableStructure
# ---------------------------------------------------------------------------

class TestTranscriptTableStructure:
    @pytest.fixture
    def table(self, qapp):
        t = TranscriptTable()
        yield t
        t.close()

    def test_column_count(self, table):
        assert table.columnCount() == 6

    def test_column_headers(self, table):
        headers = [table.horizontalHeaderItem(i).text() for i in range(6)]
        assert headers == ["#", "Start", "End", "English", "Vietnamese", "▶"]

    def test_initially_empty(self, table):
        assert table.rowCount() == 0

    def test_vertical_header_hidden(self, table):
        assert not table.verticalHeader().isVisible()


# ---------------------------------------------------------------------------
# TestTranscriptTableLoad
# ---------------------------------------------------------------------------

class TestTranscriptTableLoad:
    @pytest.fixture
    def table(self, qapp):
        t = TranscriptTable()
        yield t
        t.close()

    def test_load_entries_sets_row_count(self, table):
        table.load_entries(make_entries(5))
        assert table.rowCount() == 5

    def test_load_entries_populates_cells(self, table):
        entries = make_entries(1)
        table.load_entries(entries)
        assert table.item(0, 3).text() == "English line 1"
        assert table.item(0, 4).text() == "Vietnamese line 1"

    def test_load_entries_clears_previous(self, table):
        table.load_entries(make_entries(5))
        table.load_entries(make_entries(2))
        assert table.rowCount() == 2

    def test_clear_entries_removes_all_rows(self, table):
        table.load_entries(make_entries(3))
        table.clear_entries()
        assert table.rowCount() == 0

    def test_get_all_entries_count(self, table):
        table.load_entries(make_entries(4))
        assert len(table.get_all_entries()) == 4

    def test_get_all_entries_content(self, table):
        table.load_entries(make_entries(1))
        entries = table.get_all_entries()
        assert entries[0].text_en == "English line 1"
        assert entries[0].text_vi == "Vietnamese line 1"

    def test_get_entry_by_row(self, table):
        table.load_entries(make_entries(3))
        e = table.get_entry(1)
        assert e.index == 2


# ---------------------------------------------------------------------------
# TestTranscriptTableEdit
# ---------------------------------------------------------------------------

class TestTranscriptTableEdit:
    @pytest.fixture
    def table(self, qapp):
        t = TranscriptTable()
        yield t
        t.close()

    def test_en_cell_is_editable(self, table):
        table.load_entries(make_entries(1))
        item = table.item(0, 3)  # EN col
        from PyQt6.QtCore import Qt
        assert item.flags() & Qt.ItemFlag.ItemIsEditable

    def test_vi_cell_is_editable(self, table):
        table.load_entries(make_entries(1))
        item = table.item(0, 4)  # VI col
        from PyQt6.QtCore import Qt
        assert item.flags() & Qt.ItemFlag.ItemIsEditable

    def test_index_cell_not_editable(self, table):
        table.load_entries(make_entries(1))
        item = table.item(0, 0)  # # col
        from PyQt6.QtCore import Qt
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)

    def test_entry_edited_signal_emitted(self, table):
        edits = []
        table.load_entries(make_entries(1))
        table.entry_edited.connect(lambda row, en, vi: edits.append((row, en, vi)))
        table.item(0, 3).setText("Updated EN")
        assert len(edits) == 1
        assert edits[0][1] == "Updated EN"

    def test_get_entry_reflects_edit(self, table):
        table.load_entries(make_entries(1))
        table.item(0, 4).setText("Xin chào thế giới")
        e = table.get_entry(0)
        assert e.text_vi == "Xin chào thế giới"


# ---------------------------------------------------------------------------
# TestTranscriptTablePlayButton
# ---------------------------------------------------------------------------

class TestTranscriptTablePlayButton:
    @pytest.fixture
    def table(self, qapp):
        t = TranscriptTable()
        yield t
        t.close()

    def test_play_button_present_per_row(self, table):
        table.load_entries(make_entries(3))
        for row in range(3):
            btn = table.cellWidget(row, 5)
            assert btn is not None

    def test_play_button_disabled_without_audio(self, table):
        table.load_entries(make_entries(1))
        btn = table.cellWidget(0, 5)
        assert not btn.isEnabled()

    def test_play_button_enabled_with_audio(self, table):
        entry = BilingualEntry(
            index=1, start="00:00:01,000", end="00:00:02,000",
            text_en="Hello", text_vi="Xin chào",
            audio_path="/tmp/audio.wav",
        )
        table.load_entries([entry])
        btn = table.cellWidget(0, 5)
        assert btn.isEnabled()

    def test_play_requested_signal(self, table, qapp):
        entry = BilingualEntry(
            index=1, start="", end="", text_en="", text_vi="",
            audio_path="/tmp/audio.wav",
        )
        received = []
        table.load_entries([entry])
        table.play_requested.connect(lambda r, a: received.append((r, a)))
        btn = table.cellWidget(0, 5)
        btn.clicked.emit(False)
        qapp.processEvents()
        assert received == [(0, "/tmp/audio.wav")]


# ---------------------------------------------------------------------------
# TestTranscriptTableFilter
# ---------------------------------------------------------------------------

class TestTranscriptTableFilter:
    @pytest.fixture
    def table(self, qapp):
        t = TranscriptTable()
        yield t
        t.close()

    def test_filter_hides_non_matching_rows(self, table):
        table.load_entries(make_entries(3))
        table.filter_rows("line 1")
        assert not table.isRowHidden(0)
        assert table.isRowHidden(1)
        assert table.isRowHidden(2)

    def test_filter_empty_shows_all(self, table):
        table.load_entries(make_entries(3))
        table.filter_rows("line 1")
        table.filter_rows("")
        for row in range(3):
            assert not table.isRowHidden(row)

    def test_filter_case_insensitive(self, table):
        table.load_entries(make_entries(3))
        table.filter_rows("ENGLISH LINE 1")
        assert not table.isRowHidden(0)

    def test_filter_matches_vi_text(self, table):
        table.load_entries(make_entries(3))
        table.filter_rows("Vietnamese line 2")
        assert table.isRowHidden(0)
        assert not table.isRowHidden(1)


# ---------------------------------------------------------------------------
# TestSummaryTab
# ---------------------------------------------------------------------------

class TestSummaryTab:
    @pytest.fixture
    def tab(self, qapp):
        t = SummaryTab()
        yield t
        t.close()

    def test_has_text_edit(self, tab):
        assert hasattr(tab, "text_edit")

    def test_initial_text_empty(self, tab):
        assert tab.get_summary() == ""

    def test_set_summary(self, tab):
        tab.set_summary("This is a summary.")
        assert tab.get_summary() == "This is a summary."

    def test_word_count_updates(self, tab):
        tab.set_summary("Hello world from VietLearn")
        assert "4 words" in tab._count_label.text()


# ---------------------------------------------------------------------------
# TestFlashcardsTab
# ---------------------------------------------------------------------------

class TestFlashcardsTab:
    @pytest.fixture
    def tab(self, qapp):
        t = FlashcardsTab()
        yield t
        t.close()

    def test_has_table(self, tab):
        assert hasattr(tab, "table")

    def test_has_add_button(self, tab):
        assert hasattr(tab, "add_btn")

    def test_has_delete_button(self, tab):
        assert hasattr(tab, "delete_btn")

    def test_delete_disabled_initially(self, tab):
        assert not tab.delete_btn.isEnabled()

    def test_table_has_two_columns(self, tab):
        assert tab.table.columnCount() == 2

    def test_add_card(self, tab):
        tab.add_card("deep learning", "học sâu")
        assert tab.card_count() == 1

    def test_add_multiple_cards(self, tab):
        tab.add_card("A", "B")
        tab.add_card("C", "D")
        assert tab.card_count() == 2

    def test_get_cards_content(self, tab):
        tab.add_card("neural network", "mạng nơ-ron")
        cards = tab.get_cards()
        assert cards[0] == ("neural network", "mạng nơ-ron")

    def test_clear_cards(self, tab):
        tab.add_card("A", "B")
        tab.clear_cards()
        assert tab.card_count() == 0

    def test_initial_card_count_zero(self, tab):
        assert tab.card_count() == 0


# ---------------------------------------------------------------------------
# TestPdfNotesTab
# ---------------------------------------------------------------------------

class TestPdfNotesTab:
    @pytest.fixture
    def tab(self, qapp):
        t = PdfNotesTab()
        yield t
        t.close()

    def test_has_text_edit(self, tab):
        assert hasattr(tab, "text_edit")

    def test_has_export_button(self, tab):
        assert hasattr(tab, "export_btn")

    def test_initial_notes_empty(self, tab):
        assert tab.get_notes() == ""

    def test_set_notes(self, tab):
        tab.set_notes("Study these key terms.")
        assert tab.get_notes() == "Study these key terms."


# ---------------------------------------------------------------------------
# TestEditorViewWidgets
# ---------------------------------------------------------------------------

class TestEditorViewWidgets:
    @pytest.fixture
    def view(self, qapp):
        v = EditorView()
        yield v
        v.close()

    def test_has_transcript_table(self, view):
        assert hasattr(view, "transcript_table")

    def test_has_export_srt_btn(self, view):
        assert hasattr(view, "export_srt_btn")

    def test_has_export_txt_btn(self, view):
        assert hasattr(view, "export_txt_btn")

    def test_has_export_csv_btn(self, view):
        assert hasattr(view, "export_csv_btn")

    def test_has_search_input(self, view):
        assert hasattr(view, "search_input")

    def test_has_tabs(self, view):
        assert hasattr(view, "tabs")

    def test_tab_count_is_three(self, view):
        assert view.tabs.count() == 3

    def test_tab_names(self, view):
        names = [view.tabs.tabText(i) for i in range(3)]
        assert names == ["Summary", "Flashcards", "PDF Notes"]

    def test_has_summary_tab(self, view):
        assert isinstance(view.summary_tab, SummaryTab)

    def test_has_flashcards_tab(self, view):
        assert isinstance(view.flashcards_tab, FlashcardsTab)

    def test_has_pdf_notes_tab(self, view):
        assert isinstance(view.pdf_notes_tab, PdfNotesTab)

    def test_initial_row_count_zero(self, view):
        assert view.row_count() == 0


# ---------------------------------------------------------------------------
# TestEditorViewLoad
# ---------------------------------------------------------------------------

class TestEditorViewLoad:
    @pytest.fixture
    def view(self, qapp):
        v = EditorView()
        yield v
        v.close()

    def test_load_entries_populates_table(self, view):
        view.load_entries(make_entries(4))
        assert view.row_count() == 4

    def test_load_entries_sets_file_label(self, view):
        view.load_entries(make_entries(3), title="lecture_01.mp4")
        assert "lecture_01.mp4" in view._file_label.text()

    def test_get_entries_returns_correct_count(self, view):
        view.load_entries(make_entries(5))
        assert len(view.get_entries()) == 5

    def test_get_entries_content(self, view):
        view.load_entries(make_entries(2))
        entries = view.get_entries()
        assert entries[0].text_en == "English line 1"

    def test_load_clears_previous(self, view):
        view.load_entries(make_entries(5))
        view.load_entries(make_entries(2))
        assert view.row_count() == 2


# ---------------------------------------------------------------------------
# TestEditorViewSearch
# ---------------------------------------------------------------------------

class TestEditorViewSearch:
    @pytest.fixture
    def view(self, qapp):
        v = EditorView()
        yield v
        v.close()

    def test_search_filters_table(self, view):
        view.load_entries(make_entries(3))
        view.search_input.setText("line 1")
        assert not view.transcript_table.isRowHidden(0)
        assert view.transcript_table.isRowHidden(1)

    def test_search_clears_filter_on_empty(self, view):
        view.load_entries(make_entries(3))
        view.search_input.setText("line 1")
        view.search_input.clear()
        for row in range(3):
            assert not view.transcript_table.isRowHidden(row)

    def test_match_label_shows_count(self, view):
        view.load_entries(make_entries(3))
        view.search_input.setText("line 1")
        assert "1/3" in view._match_label.text()

    def test_match_label_empty_when_no_search(self, view):
        view.load_entries(make_entries(3))
        assert view._match_label.text() == ""


# ---------------------------------------------------------------------------
# TestEditorViewExport
# ---------------------------------------------------------------------------

class TestEditorViewExport:
    @pytest.fixture
    def view(self, qapp):
        v = EditorView()
        yield v
        v.close()

    def test_export_srt_content(self, view, tmp_path):
        view.load_entries(make_entries(2))
        path = str(tmp_path / "out.srt")
        view._do_export_srt(path)
        content = open(path, encoding="utf-8").read()
        assert "Vietnamese line 1" in content
        assert "-->" in content

    def test_export_txt_content(self, view, tmp_path):
        view.load_entries(make_entries(2))
        path = str(tmp_path / "out.txt")
        view._do_export_txt(path)
        content = open(path, encoding="utf-8").read()
        assert "English line 1" in content
        assert "Vietnamese line 1" in content

    def test_export_csv_content(self, view, tmp_path):
        view.load_entries(make_entries(2))
        path = str(tmp_path / "out.csv")
        view._do_export_csv(path)
        import csv
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["#", "Start", "End", "English", "Vietnamese"]
        assert rows[1][3] == "English line 1"
        assert rows[1][4] == "Vietnamese line 1"

    def test_export_srt_two_entries(self, view, tmp_path):
        view.load_entries(make_entries(2))
        path = str(tmp_path / "out.srt")
        view._do_export_srt(path)
        content = open(path, encoding="utf-8").read()
        assert "Vietnamese line 2" in content

    def test_export_csv_has_header_row(self, view, tmp_path):
        view.load_entries(make_entries(1))
        path = str(tmp_path / "out.csv")
        view._do_export_csv(path)
        first_line = open(path, encoding="utf-8").readline().strip()
        assert first_line == "#,Start,End,English,Vietnamese"
