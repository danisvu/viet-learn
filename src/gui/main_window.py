"""VietLearn main application window."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from src.gui.sidebar import NAV_ITEMS, Sidebar
from src.gui.views.dlai_view import DLAIView
from src.gui.views.editor_view import EditorView
from src.gui.views.glossary_view import GlossaryView
from src.gui.views.history_view import HistoryView
from src.gui.views.settings_view import SettingsView
from src.gui.views.udemy_view import UdemyView
from src.gui.views.youtube_view import YouTubeView

# Maps internal name → view class, in sidebar order
_VIEW_REGISTRY: list[tuple[str, type[QWidget]]] = [
    ("youtube",  YouTubeView),
    ("dlai",     DLAIView),
    ("udemy",    UdemyView),
    ("history",  HistoryView),
    ("glossary", GlossaryView),
    ("editor",   EditorView),
    ("settings", SettingsView),
]

_WINDOW_STYLE = """
QMainWindow {
    background-color: #181825;
}
QWidget#content-root {
    background-color: #181825;
}
QStackedWidget {
    background-color: #181825;
}
"""


class MainWindow(QMainWindow):
    """Top-level application window.

    Layout::

        ┌─ sidebar (200 px fixed) ─┬─── stacked views (stretch) ───┐
        │  VietLearn               │                                │
        │  ─────────────────────   │   <current view widget>        │
        │  YouTube                 │                                │
        │  DeepLearning.AI         │                                │
        │  Udemy                   │                                │
        │  History                 │                                │
        │  Glossary                │                                │
        │  Settings                │                                │
        └──────────────────────────┴────────────────────────────────┘

    Switching tabs: :meth:`switch_to` or click a sidebar button.
    The active view name is exposed via :meth:`current_view_name`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VietLearn")
        self.setMinimumSize(960, 640)
        self.setStyleSheet(_WINDOW_STYLE)

        # ── root widget ──────────────────────────────────────────────
        root = QWidget()
        root.setObjectName("content-root")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── sidebar ──────────────────────────────────────────────────
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        # ── stacked content area ─────────────────────────────────────
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        # ── instantiate and register views ───────────────────────────
        self._views: dict[str, QWidget] = {}
        for name, ViewClass in _VIEW_REGISTRY:
            view = ViewClass()
            self.stack.addWidget(view)
            self._views[name] = view

        # ── wire sidebar signal ──────────────────────────────────────
        self.sidebar.nav_changed.connect(self._on_nav_changed)

        # ── default to first tab ─────────────────────────────────────
        self.sidebar.select("youtube")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def switch_to(self, name: str) -> None:
        """Switch to the view identified by *name*."""
        self.sidebar.select(name)

    def current_view_name(self) -> str:
        """Return the name key of the currently visible view."""
        current = self.stack.currentWidget()
        for name, view in self._views.items():
            if view is current:
                return name
        return ""

    def view(self, name: str) -> QWidget | None:
        """Return the view widget for *name* (used in tests)."""
        return self._views.get(name)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_nav_changed(self, name: str) -> None:
        view = self._views.get(name)
        if view is not None:
            self.stack.setCurrentWidget(view)


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

def app_main() -> None:
    """Launch the VietLearn GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("VietLearn")
    app.setOrganizationName("VietLearn")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
