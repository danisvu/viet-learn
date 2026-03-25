"""DeepLearning.AI tab — manual video + subtitle file import."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView
from src.gui.views._drop_zone import FileDropZone


class DLAIView(BaseView):
    """View for importing DeepLearning.AI lecture files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="DeepLearning.AI",
            subtitle="Import lecture video + subtitle file (SRT or VTT)",
            parent=parent,
        )

        content = self.content_area()

        # ── Drag-and-drop zone ────────────────────────────────────────
        self.drop_zone = FileDropZone()
        self.drop_zone.video_dropped.connect(self._on_video_dropped)
        self.drop_zone.subtitle_dropped.connect(self._on_subtitle_dropped)
        self.drop_zone.error.connect(self._on_drop_error)
        content.addWidget(self.drop_zone)
        content.addSpacing(10)

        # ── File pickers ──────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)

        # Video picker
        video_row = QHBoxLayout()
        video_row.setSpacing(6)
        self.video_path = QLineEdit()
        self.video_path.setPlaceholderText("Select video file (.mp4, .webm, .mkv)…")
        self.video_path.setReadOnly(True)
        video_row.addWidget(self.video_path, stretch=1)
        self.video_browse_btn = QPushButton("Browse…")
        self.video_browse_btn.setObjectName("secondary-btn")
        self.video_browse_btn.setFixedWidth(90)
        self.video_browse_btn.clicked.connect(self._browse_video)
        video_row.addWidget(self.video_browse_btn)
        form.addRow("Video file:", video_row)

        # Subtitle picker
        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        self.sub_path = QLineEdit()
        self.sub_path.setPlaceholderText("Select subtitle file (.srt or .vtt)…")
        self.sub_path.setReadOnly(True)
        sub_row.addWidget(self.sub_path, stretch=1)
        self.sub_browse_btn = QPushButton("Browse…")
        self.sub_browse_btn.setObjectName("secondary-btn")
        self.sub_browse_btn.setFixedWidth(90)
        self.sub_browse_btn.clicked.connect(self._browse_subtitle)
        sub_row.addWidget(self.sub_browse_btn)
        form.addRow("Subtitle:", sub_row)

        content.addLayout(form)
        content.addSpacing(12)

        # ── Status label ──────────────────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setObjectName("status-label")
        content.addWidget(self.status_label)

        content.addStretch()

        # ── Import button ─────────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.import_btn = QPushButton("Import & Process")
        self.import_btn.setObjectName("primary-btn")
        self.import_btn.setFixedWidth(160)
        action_row.addWidget(self.import_btn)
        content.addLayout(action_row)

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.webm *.mkv);;All Files (*)",
        )
        if path:
            self.video_path.setText(path)

    def _browse_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Subtitle File",
            "",
            "Subtitle Files (*.srt *.vtt);;All Files (*)",
        )
        if path:
            self.sub_path.setText(path)

    def _on_video_dropped(self, path: str) -> None:
        self.video_path.setText(path)
        self.status_label.setText("")

    def _on_subtitle_dropped(self, path: str) -> None:
        self.sub_path.setText(path)
        self.status_label.setText("")

    def _on_drop_error(self, message: str) -> None:
        self.status_label.setText(message)
