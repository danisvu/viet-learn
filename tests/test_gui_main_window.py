"""Tests for src/gui — instantiation, navigation, and widget structure.

PyQt6 is run in offscreen mode so no display is required.
"""
from __future__ import annotations

import os

# Must be set before any PyQt6 import
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton, QStackedWidget, QWidget

# ── Shared QApplication (one per process) ────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Imports under test ────────────────────────────────────────────────────────

from src.gui.main_window import MainWindow
from src.gui.sidebar import NAV_ITEMS, Sidebar
from src.gui.views._base import BaseView
from src.gui.views.dlai_view import DLAIView
from src.gui.views.editor_view import EditorView
from src.gui.views.glossary_view import GlossaryView
from src.gui.views.history_view import HistoryView
from src.gui.views.settings_view import SettingsView
from src.gui.views.udemy_view import UdemyView
from src.gui.views.youtube_view import YouTubeView

_ALL_NAV_NAMES = [name for name, _ in NAV_ITEMS]
_VIEW_MAP: dict[str, type[BaseView]] = {
    "youtube":  YouTubeView,
    "dlai":     DLAIView,
    "udemy":    UdemyView,
    "history":  HistoryView,
    "glossary": GlossaryView,
    "editor":   EditorView,
    "settings": SettingsView,
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def window(qapp):
    w = MainWindow()
    yield w
    w.close()


@pytest.fixture
def sidebar(qapp):
    s = Sidebar()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# TestSidebar
# ---------------------------------------------------------------------------

class TestSidebar:
    def test_has_correct_number_of_buttons(self, sidebar):
        assert len(_ALL_NAV_NAMES) == 7
        for name in _ALL_NAV_NAMES:
            assert sidebar.button(name) is not None

    def test_all_buttons_are_checkable(self, sidebar):
        for name in _ALL_NAV_NAMES:
            assert sidebar.button(name).isCheckable()

    def test_nav_names_returns_all_keys(self, sidebar):
        assert sidebar.nav_names() == _ALL_NAV_NAMES

    def test_select_emits_nav_changed(self, sidebar):
        received = []
        sidebar.nav_changed.connect(received.append)
        sidebar.select("history")
        assert "history" in received

    def test_select_checks_the_button(self, sidebar):
        sidebar.select("glossary")
        assert sidebar.button("glossary").isChecked()

    def test_only_one_button_checked_at_a_time(self, sidebar):
        sidebar.select("youtube")
        sidebar.select("settings")
        checked = [
            name for name in _ALL_NAV_NAMES
            if sidebar.button(name).isChecked()
        ]
        assert checked == ["settings"]

    def test_current_name_reflects_selection(self, sidebar):
        sidebar.select("udemy")
        assert sidebar.current_name() == "udemy"

    def test_fixed_width_is_200(self, sidebar):
        assert sidebar.width() == 200

    def test_select_unknown_name_does_not_raise(self, sidebar):
        sidebar.select("nonexistent")  # should be a no-op


# ---------------------------------------------------------------------------
# TestMainWindowStructure
# ---------------------------------------------------------------------------

class TestMainWindowStructure:
    def test_window_title(self, window):
        assert window.windowTitle() == "VietLearn"

    def test_minimum_width_at_least_960(self, window):
        assert window.minimumWidth() >= 960

    def test_minimum_height_at_least_640(self, window):
        assert window.minimumHeight() >= 640

    def test_has_sidebar_attribute(self, window):
        assert isinstance(window.sidebar, Sidebar)

    def test_has_stack_attribute(self, window):
        assert isinstance(window.stack, QStackedWidget)

    def test_stack_has_six_widgets(self, window):
        assert window.stack.count() == 7

    def test_all_view_names_registered(self, window):
        for name in _ALL_NAV_NAMES:
            assert window.view(name) is not None

    def test_view_returns_none_for_unknown_name(self, window):
        assert window.view("bogus") is None


# ---------------------------------------------------------------------------
# TestMainWindowNavigation
# ---------------------------------------------------------------------------

class TestMainWindowNavigation:
    def test_default_view_is_youtube(self, window):
        assert window.current_view_name() == "youtube"

    def test_switch_to_changes_current_view(self, window):
        window.switch_to("history")
        assert window.current_view_name() == "history"

    def test_switch_to_all_views(self, window):
        for name in _ALL_NAV_NAMES:
            window.switch_to(name)
            assert window.current_view_name() == name

    def test_switch_updates_sidebar_selection(self, window):
        window.switch_to("glossary")
        assert window.sidebar.current_name() == "glossary"

    def test_repeated_switch_to_same_view(self, window):
        window.switch_to("settings")
        window.switch_to("settings")
        assert window.current_view_name() == "settings"

    def test_switch_to_unknown_does_not_crash(self, window):
        original = window.current_view_name()
        window.switch_to("nonexistent")
        # View must not change for an unknown name
        assert window.current_view_name() == original


# ---------------------------------------------------------------------------
# TestViewTypes
# ---------------------------------------------------------------------------

class TestViewTypes:
    def test_each_view_is_qwidget(self, window):
        for name in _ALL_NAV_NAMES:
            assert isinstance(window.view(name), QWidget)

    def test_each_view_is_base_view(self, window):
        for name in _ALL_NAV_NAMES:
            assert isinstance(window.view(name), BaseView)

    def test_views_are_correct_types(self, window):
        for name, cls in _VIEW_MAP.items():
            assert isinstance(window.view(name), cls)


# ---------------------------------------------------------------------------
# TestYouTubeView
# ---------------------------------------------------------------------------

class TestYouTubeView:
    def test_has_url_input(self, qapp):
        v = YouTubeView()
        assert hasattr(v, "url_input")

    def test_has_add_button(self, qapp):
        v = YouTubeView()
        assert hasattr(v, "add_btn")

    def test_has_download_button(self, qapp):
        v = YouTubeView()
        assert hasattr(v, "download_btn")

    def test_has_queue_table(self, qapp):
        v = YouTubeView()
        assert hasattr(v, "queue_table")


# ---------------------------------------------------------------------------
# TestDLAIView
# ---------------------------------------------------------------------------

class TestDLAIView:
    def test_has_video_path_input(self, qapp):
        v = DLAIView()
        assert hasattr(v, "video_path")

    def test_has_subtitle_path_input(self, qapp):
        v = DLAIView()
        assert hasattr(v, "sub_path")

    def test_has_import_button(self, qapp):
        v = DLAIView()
        assert hasattr(v, "import_btn")

    def test_video_path_is_readonly(self, qapp):
        v = DLAIView()
        assert v.video_path.isReadOnly()

    def test_sub_path_is_readonly(self, qapp):
        v = DLAIView()
        assert v.sub_path.isReadOnly()


# ---------------------------------------------------------------------------
# TestUdemyView
# ---------------------------------------------------------------------------

class TestUdemyView:
    def test_has_url_input(self, qapp):
        v = UdemyView()
        assert hasattr(v, "url_input")

    def test_has_ytdlp_radio(self, qapp):
        v = UdemyView()
        assert hasattr(v, "radio_ytdlp")

    def test_has_capture_radio(self, qapp):
        v = UdemyView()
        assert hasattr(v, "radio_capture")

    def test_ytdlp_is_default_method(self, qapp):
        v = UdemyView()
        assert v.selected_method() == "ytdlp"

    def test_selected_method_returns_capture(self, qapp):
        v = UdemyView()
        v.radio_capture.setChecked(True)
        assert v.selected_method() == "capture"

    def test_has_browser_combo(self, qapp):
        v = UdemyView()
        assert hasattr(v, "browser_combo")

    def test_browser_combo_default_is_chrome(self, qapp):
        v = UdemyView()
        assert v.selected_browser() == "chrome"


# ---------------------------------------------------------------------------
# TestHistoryView
# ---------------------------------------------------------------------------

class TestHistoryView:
    def test_has_search_input(self, qapp):
        v = HistoryView()
        assert hasattr(v, "search_input")

    def test_has_table(self, qapp):
        v = HistoryView()
        assert hasattr(v, "table")

    def test_table_has_five_columns(self, qapp):
        v = HistoryView()
        assert v.table.columnCount() == 5

    def test_open_button_disabled_initially(self, qapp):
        v = HistoryView()
        assert not v.open_btn.isEnabled()


# ---------------------------------------------------------------------------
# TestGlossaryView
# ---------------------------------------------------------------------------

class TestGlossaryView:
    def test_has_search_input(self, qapp):
        v = GlossaryView()
        assert hasattr(v, "search_input")

    def test_has_table(self, qapp):
        v = GlossaryView()
        assert hasattr(v, "table")

    def test_table_has_three_columns(self, qapp):
        v = GlossaryView()
        assert v.table.columnCount() == 3

    def test_has_add_button(self, qapp):
        v = GlossaryView()
        assert hasattr(v, "add_btn")

    def test_edit_delete_disabled_initially(self, qapp):
        v = GlossaryView()
        assert not v.edit_btn.isEnabled()
        assert not v.delete_btn.isEnabled()


# ---------------------------------------------------------------------------
# TestSettingsView
# ---------------------------------------------------------------------------

class TestSettingsView:
    def test_has_ollama_url(self, qapp):
        v = SettingsView()
        assert hasattr(v, "ollama_url")

    def test_ollama_url_default(self, qapp):
        v = SettingsView()
        assert "11434" in v.ollama_url.text()

    def test_has_whisper_model_selector(self, qapp):
        v = SettingsView()
        assert hasattr(v, "whisper_model")

    def test_has_tts_speed(self, qapp):
        v = SettingsView()
        assert hasattr(v, "tts_speed")

    def test_tts_speed_default(self, qapp):
        v = SettingsView()
        assert v.tts_speed.value() == pytest.approx(1.0)

    def test_has_save_button(self, qapp):
        v = SettingsView()
        assert hasattr(v, "save_btn")
