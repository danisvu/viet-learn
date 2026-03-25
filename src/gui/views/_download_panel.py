"""Active download progress panel and subtitle preview widget."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
)

_BAR_STYLE = """
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 6px;
    text-align: center;
    color: #cdd6f4;
    font-size: 10px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 6px;
}
"""

_PANEL_STYLE = """
QFrame#active-panel {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
}
"""


def _format_eta(eta_secs: int) -> str:
    """Format seconds as 'Xm Ys' or 'Xs'; return '–' for zero/negative."""
    if eta_secs <= 0:
        return "–"
    m, s = divmod(int(eta_secs), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def _format_speed(bps: float) -> str:
    """Format bytes/sec as a human-readable string."""
    if bps <= 0:
        return ""
    mb = bps / (1024 * 1024)
    return f"{mb:.1f} MB/s" if mb >= 0.1 else f"{bps / 1024:.0f} KB/s"


class ActiveDownloadPanel(QFrame):
    """Step indicator + progress bar + ETA/speed display.

    Hidden by default; shown by YouTubeView when a download starts.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("active-panel")
        self.setStyleSheet(_PANEL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Row 1: step label (left) + ETA/speed (right)
        info_row = QHBoxLayout()
        self._step_label = QLabel("Waiting…")
        self._step_label.setObjectName("status-label")
        info_row.addWidget(self._step_label, stretch=1)

        self._eta_label = QLabel("")
        self._eta_label.setObjectName("status-label")
        self._eta_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        info_row.addWidget(self._eta_label)
        layout.addLayout(info_row)

        # Row 2: progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setFixedHeight(14)
        self._bar.setStyleSheet(_BAR_STYLE)
        layout.addWidget(self._bar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_step(self, step_text: str) -> None:
        """Set the step indicator label."""
        self._step_label.setText(step_text)

    def update_byte_progress(
        self, downloaded: int, total: int, eta_secs: int, speed: float
    ) -> None:
        """Update progress bar percentage and ETA/speed label."""
        if total > 0:
            self._bar.setRange(0, 100)
            self._bar.setValue(min(100, int(downloaded * 100 / total)))
        else:
            self._bar.setRange(0, 0)  # indeterminate

        parts: list[str] = []
        eta = _format_eta(eta_secs)
        if eta != "–":
            parts.append(f"ETA {eta}")
        spd = _format_speed(speed)
        if spd:
            parts.append(spd)
        self._eta_label.setText("  ·  ".join(parts))

    def set_indeterminate(self) -> None:
        """Show a busy/indeterminate progress bar."""
        self._bar.setRange(0, 0)

    def set_complete(self) -> None:
        """Snap progress bar to 100% and clear ETA."""
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self._eta_label.setText("")

    def reset(self) -> None:
        """Reset to initial state (called before each batch starts)."""
        self._step_label.setText("Starting…")
        self._eta_label.setText("")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)

    # ------------------------------------------------------------------
    # Test-friendly accessors
    # ------------------------------------------------------------------

    @property
    def step_text(self) -> str:
        return self._step_label.text()

    @property
    def eta_text(self) -> str:
        return self._eta_label.text()

    @property
    def bar_value(self) -> int:
        return self._bar.value()

    @property
    def bar_maximum(self) -> int:
        return self._bar.maximum()


class SubtitlePreviewPanel(QGroupBox):
    """Read-only text pane showing the first few subtitle entries.

    Hidden by default; shown by YouTubeView when subtitle data arrives.
    """

    _MAX_CHARS = 800

    def __init__(self, parent=None) -> None:
        super().__init__("Subtitle Preview", parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._edit = QTextEdit()
        self._edit.setReadOnly(True)
        self._edit.setFixedHeight(110)
        self._edit.setPlaceholderText(
            "Subtitle preview will appear here after download completes…"
        )
        self._edit.setFont(QFont("Menlo, Consolas, monospace", 10))
        self._edit.setStyleSheet(
            "QTextEdit { background-color: #181825; color: #cdd6f4;"
            " border: none; font-size: 11px; }"
        )
        layout.addWidget(self._edit)

    def show_preview(self, text: str) -> None:
        """Display *text* (capped at _MAX_CHARS) in the preview pane."""
        self._edit.setPlainText(text[: self._MAX_CHARS])

    def clear(self) -> None:
        """Clear the preview text."""
        self._edit.clear()

    @property
    def preview_text(self) -> str:
        return self._edit.toPlainText()
