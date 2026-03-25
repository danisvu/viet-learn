"""Shared base widget for all content views."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_VIEW_STYLE = """
BaseView {
    background-color: #181825;
}
QLabel#view-title {
    color: #cdd6f4;
    font-size: 20px;
    font-weight: bold;
    background: transparent;
}
QLabel#view-subtitle {
    color: #6c7086;
    font-size: 12px;
    background: transparent;
}
QLabel#section-label {
    color: #a6adc8;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
    padding-top: 4px;
}
QLabel#status-label {
    color: #6c7086;
    font-size: 11px;
    background: transparent;
}
QLineEdit#url-input {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit#url-input:focus {
    border-color: #89b4fa;
}
QPushButton#primary-btn {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#primary-btn:hover {
    background-color: #b4d0ff;
}
QPushButton#primary-btn:pressed {
    background-color: #6c9fdf;
}
QPushButton#secondary-btn {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton#secondary-btn:hover {
    background-color: #45475a;
}
QPushButton#danger-btn {
    background-color: #313244;
    color: #f38ba8;
    border: 1px solid #f38ba8;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton#danger-btn:hover {
    background-color: #f38ba820;
}
QGroupBox {
    color: #a6adc8;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 10px;
    padding: 12px 8px 8px;
    background-color: #1e1e2e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: #89b4fa;
}
QTableWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    gridline-color: #313244;
    border: 1px solid #313244;
    border-radius: 6px;
    font-size: 12px;
}
QTableWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}
QHeaderView::section {
    background-color: #181825;
    color: #6c7086;
    border: none;
    border-bottom: 1px solid #313244;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QListWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    font-size: 12px;
}
QListWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}
QScrollArea {
    background: transparent;
    border: none;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}
QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 13px;
}
QRadioButton {
    color: #cdd6f4;
    font-size: 13px;
    background: transparent;
}
"""


class BaseView(QWidget):
    """Base class for all content view widgets.

    Provides a standard header (title + subtitle) and a :meth:`content_area`
    that returns the ``QVBoxLayout`` where subclasses add their specific widgets.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(_VIEW_STYLE)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(32, 28, 32, 24)
        self._root_layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        title_label = QLabel(title)
        title_label.setObjectName("view-title")
        self._root_layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("view-subtitle")
            sub_label.setWordWrap(True)
            self._root_layout.addWidget(sub_label)

        # Thin divider beneath header
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(
            "background-color: #313244; max-height: 1px; margin: 14px 0 18px;"
        )
        self._root_layout.addWidget(sep)

        # ── Content area ──────────────────────────────────────────────
        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(10)
        self._root_layout.addLayout(self._content_layout)

    def content_area(self) -> QVBoxLayout:
        """Return the ``QVBoxLayout`` for view-specific content."""
        return self._content_layout
