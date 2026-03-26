"""Left navigation sidebar with exclusive nav buttons."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# (internal_name, display_label)
NAV_ITEMS: list[tuple[str, str]] = [
    ("youtube",  "YouTube"),
    ("dlai",     "DeepLearning.AI"),
    ("udemy",    "Udemy"),
    ("history",  "History"),
    ("search",   "Search"),
    ("glossary", "Glossary"),
    ("editor",   "Transcript Editor"),
    ("settings", "Settings"),
]

_STYLE = """
Sidebar {
    background-color: #1e1e2e;
    border-right: 1px solid #313244;
}
QLabel#app-title {
    color: #cdd6f4;
    font-size: 17px;
    font-weight: bold;
    padding: 22px 18px 18px;
    background: transparent;
    letter-spacing: 1px;
}
QLabel#app-subtitle {
    color: #6c7086;
    font-size: 10px;
    padding: 0 18px 14px;
    background: transparent;
}
QPushButton[nav="true"] {
    text-align: left;
    padding: 11px 20px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0;
    font-size: 13px;
    color: #a6adc8;
    background: transparent;
}
QPushButton[nav="true"]:hover {
    background-color: #2a2a3e;
    color: #cdd6f4;
}
QPushButton[nav="true"]:checked {
    background-color: #2a2a3e;
    color: #89b4fa;
    border-left: 3px solid #89b4fa;
    font-weight: 600;
}
"""


class Sidebar(QWidget):
    """Vertical navigation sidebar.

    Emits :attr:`nav_changed` (str) whenever a different tab is selected.
    The signal carries the internal name key (e.g. ``"youtube"``).
    """

    nav_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(200)
        self.setStyleSheet(_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # App branding
        title = QLabel("VietLearn")
        title.setObjectName("app-title")
        root.addWidget(title)

        subtitle = QLabel("AI Video Translator")
        subtitle.setObjectName("app-subtitle")
        root.addWidget(subtitle)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #313244; max-height: 1px; margin: 0;")
        root.addWidget(sep)

        # Navigation buttons
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for name, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setProperty("nav", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(42)
            self._group.addButton(btn)
            self._buttons[name] = btn
            root.addWidget(btn)
            # Capture `name` by default-argument binding to avoid closure pitfall
            btn.clicked.connect(lambda _checked, n=name: self.nav_changed.emit(n))

        root.addStretch()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def select(self, name: str) -> None:
        """Programmatically activate the nav item for *name*."""
        btn = self._buttons.get(name)
        if btn is None:
            return
        if not btn.isChecked():
            btn.setChecked(True)
        self.nav_changed.emit(name)

    def current_name(self) -> str:
        """Return the name key of the currently checked nav button."""
        checked = self._group.checkedButton()
        for name, btn in self._buttons.items():
            if btn is checked:
                return name
        return ""

    def button(self, name: str) -> QPushButton | None:
        """Return the QPushButton for *name* (used in tests)."""
        return self._buttons.get(name)

    def nav_names(self) -> list[str]:
        """Return the ordered list of all nav item name keys."""
        return [name for name, _ in NAV_ITEMS]
