"""Udemy tab — yt-dlp download or BlackHole audio capture fallback."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView

_BROWSERS = ["chrome", "firefox", "safari", "edge", "brave"]


class UdemyView(BaseView):
    """View for downloading Udemy lectures (yt-dlp or BlackHole capture)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Udemy",
            subtitle="Download via yt-dlp (Plan A) or capture audio via BlackHole (Plan B)",
            parent=parent,
        )

        content = self.content_area()

        # ── URL input ─────────────────────────────────────────────────
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste Udemy lecture URL…")
        self.url_input.setObjectName("url-input")
        url_row.addWidget(self.url_input, stretch=1)
        content.addLayout(url_row)
        content.addSpacing(16)

        # ── Method selector ───────────────────────────────────────────
        method_group = QGroupBox("Download Method")
        method_group.setObjectName("method-group")
        method_layout = QVBoxLayout(method_group)
        method_layout.setSpacing(8)

        self._method_buttons = QButtonGroup(self)
        self._method_buttons.setExclusive(True)

        self.radio_ytdlp = QRadioButton(
            "Plan A — yt-dlp + browser cookies  (recommended)"
        )
        self.radio_ytdlp.setChecked(True)
        self._method_buttons.addButton(self.radio_ytdlp, 0)
        method_layout.addWidget(self.radio_ytdlp)

        self.radio_capture = QRadioButton(
            "Plan B — BlackHole audio capture  (DRM fallback)"
        )
        self._method_buttons.addButton(self.radio_capture, 1)
        method_layout.addWidget(self.radio_capture)

        content.addWidget(method_group)
        content.addSpacing(12)

        # ── Browser picker (Plan A only) ──────────────────────────────
        browser_form = QFormLayout()
        browser_form.setSpacing(8)
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(_BROWSERS)
        self.browser_combo.setFixedWidth(140)
        browser_form.addRow("Browser for cookies:", self.browser_combo)
        content.addLayout(browser_form)

        # Toggle browser picker based on method
        self.radio_capture.toggled.connect(
            lambda checked: self.browser_combo.setEnabled(not checked)
        )

        content.addStretch()

        # ── Status ────────────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setObjectName("status-label")
        content.addWidget(self.status_label)

        # ── Action row ────────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primary-btn")
        self.start_btn.setFixedWidth(110)
        action_row.addWidget(self.start_btn)

        content.addLayout(action_row)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def selected_method(self) -> str:
        """Return ``"ytdlp"`` or ``"capture"``."""
        return "capture" if self.radio_capture.isChecked() else "ytdlp"

    def selected_browser(self) -> str:
        return self.browser_combo.currentText()
