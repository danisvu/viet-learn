"""Tests for GlossaryView — CRUD, pack filter, search, import/export JSON.

PyQt6 runs offscreen — no display required.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.models import GlossaryMode, GlossaryTerm
from src.gui.views.glossary_view import GlossaryView
from src.gui.views._glossary_dialog import GlossaryDialog, PACKS, MODES


# ── Shared QApplication ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(qapp):
    v = GlossaryView()
    yield v
    v.close()


# ── Sample data helpers ───────────────────────────────────────────────────────

def _term(en="gradient descent", vi="giảm dần độ dốc",
          mode=GlossaryMode.REPLACE, pack="AI/ML") -> GlossaryTerm:
    return GlossaryTerm(english=en, vietnamese=vi, mode=mode, pack=pack)


def _sample_terms() -> list[GlossaryTerm]:
    return [
        GlossaryTerm("gradient descent", "giảm dần độ dốc", GlossaryMode.REPLACE, "AI/ML"),
        GlossaryTerm("neural network",   "mạng nơ-ron",      GlossaryMode.REPLACE, "AI/ML"),
        GlossaryTerm("for loop",         "vòng lặp for",     GlossaryMode.REPLACE, "Programming"),
        GlossaryTerm("integral",         "tích phân",        GlossaryMode.REPLACE, "Math"),
        GlossaryTerm("backpropagation",  "",                 GlossaryMode.KEEP_ENGLISH, "AI/ML"),
        GlossaryTerm("custom term",      "thuật ngữ tùy chỉnh", GlossaryMode.REPLACE, "Custom"),
    ]


# ---------------------------------------------------------------------------
# TestGlossaryViewWidgets
# ---------------------------------------------------------------------------

class TestGlossaryViewWidgets:
    def test_has_search_input(self, view):
        assert hasattr(view, "search_input")

    def test_has_pack_filter(self, view):
        assert hasattr(view, "pack_filter")

    def test_has_add_btn(self, view):
        assert hasattr(view, "add_btn")

    def test_has_table(self, view):
        assert hasattr(view, "table")

    def test_table_has_four_columns(self, view):
        assert view.table.columnCount() == 4

    def test_table_column_headers(self, view):
        headers = [view.table.horizontalHeaderItem(i).text() for i in range(4)]
        assert headers == ["English Term", "Vietnamese", "Mode", "Pack"]

    def test_has_count_label(self, view):
        assert hasattr(view, "count_label")

    def test_has_edit_btn(self, view):
        assert hasattr(view, "edit_btn")

    def test_has_delete_btn(self, view):
        assert hasattr(view, "delete_btn")

    def test_has_import_btn(self, view):
        assert hasattr(view, "import_btn")

    def test_has_export_btn(self, view):
        assert hasattr(view, "export_btn")

    def test_edit_disabled_initially(self, view):
        assert not view.edit_btn.isEnabled()

    def test_delete_disabled_initially(self, view):
        assert not view.delete_btn.isEnabled()

    def test_pack_filter_has_all_option(self, view):
        items = [view.pack_filter.itemText(i) for i in range(view.pack_filter.count())]
        assert "All" in items

    def test_pack_filter_options(self, view):
        items = [view.pack_filter.itemText(i) for i in range(view.pack_filter.count())]
        for pack in ["All", "AI/ML", "Programming", "Math", "Custom"]:
            assert pack in items


# ---------------------------------------------------------------------------
# TestGlossaryViewLoadAndCount
# ---------------------------------------------------------------------------

class TestGlossaryViewLoadAndCount:
    def test_initially_empty(self, view):
        assert view.term_count() == 0

    def test_load_terms_sets_count(self, view):
        view.load_terms(_sample_terms())
        assert view.term_count() == 6

    def test_load_terms_sets_row_count(self, view):
        view.load_terms(_sample_terms())
        assert view.table.rowCount() == 6

    def test_load_terms_populates_cells(self, view):
        view.load_terms([_term("backprop", "lan truyền ngược")])
        assert view.table.item(0, 0).text() == "backprop"
        assert view.table.item(0, 1).text() == "lan truyền ngược"

    def test_load_terms_shows_pack_column(self, view):
        view.load_terms([_term(pack="Math")])
        assert view.table.item(0, 3).text() == "Math"

    def test_load_terms_shows_mode_column(self, view):
        view.load_terms([_term(mode=GlossaryMode.KEEP_ENGLISH)])
        assert view.table.item(0, 2).text() == GlossaryMode.KEEP_ENGLISH.value

    def test_load_terms_replaces_previous(self, view):
        view.load_terms(_sample_terms())
        view.load_terms([_term()])
        assert view.term_count() == 1

    def test_count_label_updates_on_load(self, view):
        view.load_terms(_sample_terms())
        assert "6" in view.count_label.text()

    def test_get_terms_returns_copy(self, view):
        view.load_terms([_term()])
        result = view.get_terms()
        assert len(result) == 1
        result.clear()
        assert view.term_count() == 1  # original unchanged

    def test_table_cells_not_editable(self, view):
        from PyQt6.QtCore import Qt
        view.load_terms([_term()])
        item = view.table.item(0, 0)
        assert not (item.flags() & Qt.ItemFlag.ItemIsEditable)


# ---------------------------------------------------------------------------
# TestPackFilter
# ---------------------------------------------------------------------------

class TestPackFilter:
    def test_filter_all_shows_all_rows(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 6

    def test_filter_aiml_shows_only_aiml(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("AI/ML")
        hidden = [view.table.isRowHidden(r) for r in range(view.table.rowCount())]
        # Rows 0,1,4 are AI/ML (indices in _sample_terms)
        visible_rows = [r for r, h in enumerate(hidden) if not h]
        for vr in visible_rows:
            assert view.table.item(vr, 3).text() == "AI/ML"

    def test_filter_programming(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("Programming")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_filter_math(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("Math")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_filter_custom(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("Custom")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_filter_count_label_shows_fraction(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("Math")
        assert "1/6" in view.count_label.text()

    def test_filter_all_count_label_shows_total(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.clear()
        assert "6 terms" in view.count_label.text()


# ---------------------------------------------------------------------------
# TestSearch
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_filters_by_english(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("gradient")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_search_filters_by_vietnamese(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("tích phân")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_search_case_insensitive(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("GRADIENT")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1

    def test_search_empty_shows_all(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("gradient")
        view.search_input.clear()
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 6

    def test_search_and_pack_combined(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("AI/ML")
        view.search_input.setText("neural")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 1
        view.search_input.clear()
        view.pack_filter.setCurrentText("All")

    def test_search_no_match_hides_all(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("xxxxnotfound")
        visible = sum(1 for r in range(view.table.rowCount())
                      if not view.table.isRowHidden(r))
        assert visible == 0
        view.search_input.clear()

    def test_search_count_label_shows_fraction(self, view):
        view.load_terms(_sample_terms())
        view.pack_filter.setCurrentText("All")
        view.search_input.setText("network")
        assert "/" in view.count_label.text()
        view.search_input.clear()


# ---------------------------------------------------------------------------
# TestDelete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_reduces_term_count(self, view):
        view.load_terms([_term("A", "a"), _term("B", "b")])
        view.table.selectRow(0)
        view._on_delete()
        assert view.term_count() == 1

    def test_delete_removes_correct_term(self, view):
        view.load_terms([_term("keep"), _term("remove")])
        view.table.selectRow(1)
        view._on_delete()
        assert view._terms[0].english == "keep"

    def test_delete_updates_table_row_count(self, view):
        view.load_terms([_term("X"), _term("Y"), _term("Z")])
        view.table.selectRow(0)
        view._on_delete()
        assert view.table.rowCount() == 2

    def test_delete_updates_count_label(self, view):
        view.load_terms([_term("A"), _term("B")])
        view.table.selectRow(0)
        view._on_delete()
        assert "1" in view.count_label.text()


# ---------------------------------------------------------------------------
# TestImportJson
# ---------------------------------------------------------------------------

class TestImportJson:
    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def test_import_adds_terms(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "epoch", "vietnamese": "kỷ nguyên", "mode": "replace", "pack": "AI/ML"},
        ])
        added = view.do_import_json(str(p))
        assert added == 1
        assert view.term_count() == 1

    def test_import_appends_to_existing(self, view, tmp_path):
        view.load_terms([_term()])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "batch", "vietnamese": "lô", "mode": "replace", "pack": "AI/ML"},
        ])
        view.do_import_json(str(p))
        assert view.term_count() == 2

    def test_import_updates_table(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "loss", "vietnamese": "mất mát", "mode": "replace", "pack": "AI/ML"},
        ])
        view.do_import_json(str(p))
        assert view.table.rowCount() == 1
        assert view.table.item(0, 0).text() == "loss"

    def test_import_defaults_missing_pack(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "bias", "vietnamese": "độ lệch", "mode": "replace"},
        ])
        view.do_import_json(str(p))
        assert view._terms[0].pack == "Custom"

    def test_import_skips_invalid_entries(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "valid", "vietnamese": "hợp lệ", "mode": "replace", "pack": "AI/ML"},
            {"bad_key": "no english"},
        ])
        added = view.do_import_json(str(p))
        assert added == 1

    def test_import_multiple_entries(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        items = [
            {"english": f"term{i}", "vietnamese": f"thuật ngữ{i}",
             "mode": "replace", "pack": "AI/ML"}
            for i in range(5)
        ]
        self._write_json(str(p), items)
        added = view.do_import_json(str(p))
        assert added == 5
        assert view.term_count() == 5

    def test_import_sets_mode(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "g.json"
        self._write_json(str(p), [
            {"english": "API", "vietnamese": "", "mode": "keep_english", "pack": "Programming"},
        ])
        view.do_import_json(str(p))
        assert view._terms[0].mode == GlossaryMode.KEEP_ENGLISH


# ---------------------------------------------------------------------------
# TestExportJson
# ---------------------------------------------------------------------------

class TestExportJson:
    def test_export_creates_file(self, view, tmp_path):
        view.load_terms([_term()])
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        assert p.exists()

    def test_export_valid_json(self, view, tmp_path):
        view.load_terms([_term()])
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_export_correct_count(self, view, tmp_path):
        view.load_terms(_sample_terms())
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 6

    def test_export_contains_english(self, view, tmp_path):
        view.load_terms([_term("overfitting", "quá khớp")])
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["english"] == "overfitting"
        assert data[0]["vietnamese"] == "quá khớp"

    def test_export_contains_pack(self, view, tmp_path):
        view.load_terms([_term(pack="Math")])
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["pack"] == "Math"

    def test_export_contains_mode(self, view, tmp_path):
        view.load_terms([_term(mode=GlossaryMode.KEEP_ENGLISH)])
        p = tmp_path / "out.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["mode"] == "keep_english"

    def test_roundtrip_import_export(self, view, tmp_path):
        """Export then re-import should produce identical terms."""
        original = _sample_terms()
        view.load_terms(original)
        p = tmp_path / "rt.json"
        view.do_export_json(str(p))

        view2 = GlossaryView()
        view2.do_import_json(str(p))
        reimported = view2.get_terms()
        view2.close()

        assert len(reimported) == len(original)
        for orig, reimp in zip(original, reimported):
            assert orig.english == reimp.english
            assert orig.vietnamese == reimp.vietnamese
            assert orig.mode == reimp.mode
            assert orig.pack == reimp.pack

    def test_export_empty_glossary(self, view, tmp_path):
        view.load_terms([])
        p = tmp_path / "empty.json"
        view.do_export_json(str(p))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        assert data == []


# ---------------------------------------------------------------------------
# TestGlossaryDialog
# ---------------------------------------------------------------------------

class TestGlossaryDialog:
    def test_has_english_input(self, qapp):
        d = GlossaryDialog()
        assert hasattr(d, "english_input")
        d.reject()

    def test_has_vietnamese_input(self, qapp):
        d = GlossaryDialog()
        assert hasattr(d, "vietnamese_input")
        d.reject()

    def test_has_mode_combo(self, qapp):
        d = GlossaryDialog()
        assert hasattr(d, "mode_combo")
        d.reject()

    def test_has_pack_combo(self, qapp):
        d = GlossaryDialog()
        assert hasattr(d, "pack_combo")
        d.reject()

    def test_mode_combo_options(self, qapp):
        d = GlossaryDialog()
        items = [d.mode_combo.itemText(i) for i in range(d.mode_combo.count())]
        for m in MODES:
            assert m in items
        d.reject()

    def test_pack_combo_options(self, qapp):
        d = GlossaryDialog()
        items = [d.pack_combo.itemText(i) for i in range(d.pack_combo.count())]
        for p in PACKS:
            assert p in items
        d.reject()

    def test_prepopulates_existing_term(self, qapp):
        term = GlossaryTerm("backprop", "lan truyền ngược", GlossaryMode.REPLACE, "AI/ML")
        d = GlossaryDialog(term=term)
        assert d.english_input.text() == "backprop"
        assert d.vietnamese_input.text() == "lan truyền ngược"
        assert d.pack_combo.currentText() == "AI/ML"
        d.reject()

    def test_get_term_builds_correct_object(self, qapp):
        d = GlossaryDialog()
        d.english_input.setText("  softmax  ")
        d.vietnamese_input.setText("softmax")
        d.mode_combo.setCurrentText(GlossaryMode.REPLACE.value)
        d.pack_combo.setCurrentText("AI/ML")
        term = d.get_term()
        assert term.english == "softmax"   # stripped
        assert term.pack == "AI/ML"
        assert term.mode == GlossaryMode.REPLACE
        d.reject()

    def test_empty_english_does_not_accept(self, qapp):
        d = GlossaryDialog()
        d.english_input.setText("")
        d._on_accept()
        assert not d.result() == GlossaryDialog.DialogCode.Accepted
        d.reject()

    def test_nonempty_english_accepts(self, qapp):
        d = GlossaryDialog()
        d.english_input.setText("loss function")
        d._on_accept()
        assert d.result() == GlossaryDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# TestGlossaryTermModel
# ---------------------------------------------------------------------------

class TestGlossaryTermModel:
    def test_default_pack_is_custom(self):
        t = GlossaryTerm("word", "từ", GlossaryMode.REPLACE)
        assert t.pack == "Custom"

    def test_explicit_pack(self):
        t = GlossaryTerm("integral", "tích phân", GlossaryMode.REPLACE, pack="Math")
        assert t.pack == "Math"

    def test_mode_keep_english(self):
        t = GlossaryTerm("API", "", GlossaryMode.KEEP_ENGLISH)
        assert t.mode == GlossaryMode.KEEP_ENGLISH

    def test_mode_translate_annotate(self):
        t = GlossaryTerm("epoch", "kỷ nguyên", GlossaryMode.TRANSLATE_ANNOTATE)
        assert t.mode == GlossaryMode.TRANSLATE_ANNOTATE
