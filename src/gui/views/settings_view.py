"""Settings tab — model selection, TTS voice, pipeline parameters."""
from __future__ import annotations

import logging
import os
import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.gui.views._base import BaseView

log = logging.getLogger(__name__)


class SettingsView(BaseView):
    """View for configuring models, voices, and pipeline parameters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Settings",
            subtitle="Model selection, TTS voice, and pipeline preferences",
            parent=parent,
        )

        content = self.content_area()

        # Wrap everything in a scroll area so it works on small screens
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("settings-scroll")
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setSpacing(16)
        inner_layout.setContentsMargins(0, 0, 16, 16)

        # ── Translation (Ollama) ──────────────────────────────────────
        ollama_box = QGroupBox("Translation (Ollama)")
        ollama_form = QFormLayout(ollama_box)
        ollama_form.setSpacing(8)

        self.ollama_url = QLineEdit("http://localhost:11434")
        ollama_form.addRow("API URL:", self.ollama_url)

        self.ollama_model = QComboBox()
        self.ollama_model.addItems(["qwen3:8b", "qwen3:30b", "llama3.1:8b"])
        self.ollama_model.setEditable(True)
        ollama_form.addRow("Model:", self.ollama_model)

        inner_layout.addWidget(ollama_box)

        # ── STT (Whisper) ─────────────────────────────────────────────
        whisper_box = QGroupBox("Speech-to-Text (Whisper.cpp)")
        whisper_form = QFormLayout(whisper_box)
        whisper_form.setSpacing(8)

        self.whisper_model = QComboBox()
        self.whisper_model.addItems([
            "large-v3-turbo", "large-v3", "medium.en", "small.en", "base.en"
        ])
        whisper_form.addRow("Model:", self.whisper_model)

        self.whisper_threads = QSpinBox()
        self.whisper_threads.setRange(1, 16)
        self.whisper_threads.setValue(4)
        self.whisper_threads.setFixedWidth(80)
        whisper_form.addRow("Threads:", self.whisper_threads)

        inner_layout.addWidget(whisper_box)

        # ── TTS (Piper) ───────────────────────────────────────────────
        tts_box = QGroupBox("Text-to-Speech (Piper TTS)")
        tts_form = QFormLayout(tts_box)
        tts_form.setSpacing(8)

        self.tts_model = QComboBox()
        self.tts_model.addItems(["vi_VN-vais1000-medium", "vi_VN-vais1000-high"])
        self.tts_model.setEditable(True)
        tts_form.addRow("Voice:", self.tts_model)

        self.tts_speed = QDoubleSpinBox()
        self.tts_speed.setRange(0.5, 2.0)
        self.tts_speed.setSingleStep(0.1)
        self.tts_speed.setValue(1.0)
        self.tts_speed.setFixedWidth(80)
        tts_form.addRow("Speed:", self.tts_speed)

        inner_layout.addWidget(tts_box)

        # ── Audio mix / Speed limits ───────────────────────────────────
        audio_box = QGroupBox("Audio Mix & Speed Limits")
        audio_form = QFormLayout(audio_box)
        audio_form.setSpacing(8)

        self.original_vol = QDoubleSpinBox()
        self.original_vol.setRange(0.0, 1.0)
        self.original_vol.setSingleStep(0.05)
        self.original_vol.setValue(0.15)
        self.original_vol.setFixedWidth(80)
        audio_form.addRow("Original audio volume:", self.original_vol)

        self.stretch_min = QDoubleSpinBox()
        self.stretch_min.setRange(0.5, 1.0)
        self.stretch_min.setSingleStep(0.05)
        self.stretch_min.setValue(0.75)
        self.stretch_min.setFixedWidth(80)
        audio_form.addRow("Min stretch ratio:", self.stretch_min)

        self.stretch_max = QDoubleSpinBox()
        self.stretch_max.setRange(1.0, 2.0)
        self.stretch_max.setSingleStep(0.05)
        self.stretch_max.setValue(1.6)
        self.stretch_max.setFixedWidth(80)
        audio_form.addRow("Max stretch ratio:", self.stretch_max)

        inner_layout.addWidget(audio_box)

        # ── Output Preferences ────────────────────────────────────────
        output_box = QGroupBox("Output Preferences")
        output_form = QFormLayout(output_box)
        output_form.setSpacing(8)

        self.output_dir = QLineEdit("output")
        output_form.addRow("Output directory:", self.output_dir)

        self.video_format = QComboBox()
        self.video_format.addItems(["mp4", "mkv", "webm"])
        output_form.addRow("Video format:", self.video_format)

        self.subtitle_format = QComboBox()
        self.subtitle_format.addItems(["srt", "vtt", "ass"])
        output_form.addRow("Subtitle format:", self.subtitle_format)

        self.keep_audio_clips = QCheckBox("Keep individual TTS audio clips")
        self.keep_audio_clips.setChecked(False)
        output_form.addRow("", self.keep_audio_clips)

        self.open_after_export = QCheckBox("Open output folder after export")
        self.open_after_export.setChecked(True)
        output_form.addRow("", self.open_after_export)

        inner_layout.addWidget(output_box)

        # ── Storage Management ────────────────────────────────────────
        storage_box = QGroupBox("Storage Management")
        storage_layout = QVBoxLayout(storage_box)
        storage_layout.setSpacing(10)

        # Disk usage row
        usage_row = QHBoxLayout()
        self._usage_label = QLabel("Calculating…")
        self._usage_label.setObjectName("status-label")
        usage_row.addWidget(QLabel("Disk usage:"))
        usage_row.addWidget(self._usage_label, stretch=1)
        self.refresh_usage_btn = QPushButton("Refresh")
        self.refresh_usage_btn.setObjectName("secondary-btn")
        self.refresh_usage_btn.setFixedWidth(80)
        usage_row.addWidget(self.refresh_usage_btn)
        storage_layout.addLayout(usage_row)

        # Cache / temp files
        cache_row = QHBoxLayout()
        cache_row.addWidget(QLabel("Temp / cache files:"))
        self._cache_label = QLabel("–")
        self._cache_label.setObjectName("status-label")
        cache_row.addWidget(self._cache_label, stretch=1)
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.setObjectName("danger-btn")
        self.clear_cache_btn.setFixedWidth(100)
        cache_row.addWidget(self.clear_cache_btn)
        storage_layout.addLayout(cache_row)

        # Downloads folder
        dl_row = QHBoxLayout()
        dl_row.addWidget(QLabel("Downloads folder:"))
        self._dl_label = QLabel("–")
        self._dl_label.setObjectName("status-label")
        dl_row.addWidget(self._dl_label, stretch=1)
        self.clear_downloads_btn = QPushButton("Clear Downloads")
        self.clear_downloads_btn.setObjectName("danger-btn")
        self.clear_downloads_btn.setFixedWidth(120)
        dl_row.addWidget(self.clear_downloads_btn)
        storage_layout.addLayout(dl_row)

        inner_layout.addWidget(storage_box)
        inner_layout.addStretch()

        scroll.setWidget(inner)
        content.addWidget(scroll, stretch=1)

        # ── Save / Reset row ──────────────────────────────────────────
        action_row = QHBoxLayout()
        action_row.addStretch()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setObjectName("secondary-btn")
        action_row.addWidget(self.reset_btn)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primary-btn")
        action_row.addWidget(self.save_btn)

        content.addLayout(action_row)

        # ── Wire signals ──────────────────────────────────────────────
        self.refresh_usage_btn.clicked.connect(self.refresh_storage_usage)
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.clear_downloads_btn.clicked.connect(self._clear_downloads)
        self.reset_btn.clicked.connect(self._reset_defaults)

        # Compute initial storage stats
        self.refresh_storage_usage()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Return current settings as a plain dict (mirrors config.yaml structure)."""
        return {
            "ollama": {
                "base_url": self.ollama_url.text().strip(),
                "model": self.ollama_model.currentText().strip(),
            },
            "whisper": {
                "model": self.whisper_model.currentText(),
                "n_threads": self.whisper_threads.value(),
            },
            "tts": {
                "model": self.tts_model.currentText().strip(),
                "speed": self.tts_speed.value(),
            },
            "audio": {
                "original_volume": self.original_vol.value(),
            },
            "time_stretch": {
                "min_speed_ratio": self.stretch_min.value(),
                "max_speed_ratio": self.stretch_max.value(),
            },
            "output": {
                "directory": self.output_dir.text().strip(),
                "video_format": self.video_format.currentText(),
                "subtitle_format": self.subtitle_format.currentText(),
                "keep_audio_clips": self.keep_audio_clips.isChecked(),
                "open_after_export": self.open_after_export.isChecked(),
            },
        }

    def refresh_storage_usage(self) -> None:
        """Re-scan output directories and update the storage labels."""
        output = self.output_dir.text().strip() or "output"
        total = _dir_size_mb(output)
        cache = _dir_size_mb(os.path.join(output, "stt")) + _dir_size_mb(
            os.path.join(output, "captures")
        )
        downloads = _dir_size_mb(os.path.join(output, "downloads"))

        self._usage_label.setText(f"{total:.1f} MB")
        self._cache_label.setText(f"{cache:.1f} MB")
        self._dl_label.setText(f"{downloads:.1f} MB")

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _clear_cache(self) -> None:
        """Delete STT and capture cache sub-folders."""
        output = self.output_dir.text().strip() or "output"
        for sub in ("stt", "captures"):
            path = os.path.join(output, sub)
            _rmtree_contents(path)
        self.refresh_storage_usage()
        log.info("Cache cleared")

    def _clear_downloads(self) -> None:
        """Delete contents of the downloads sub-folder."""
        output = self.output_dir.text().strip() or "output"
        _rmtree_contents(os.path.join(output, "downloads"))
        self.refresh_storage_usage()
        log.info("Downloads cleared")

    def _reset_defaults(self) -> None:
        """Restore all fields to their default values."""
        self.ollama_url.setText("http://localhost:11434")
        self.ollama_model.setCurrentText("qwen3:8b")
        self.whisper_model.setCurrentIndex(0)
        self.whisper_threads.setValue(4)
        self.tts_model.setCurrentText("vi_VN-vais1000-medium")
        self.tts_speed.setValue(1.0)
        self.original_vol.setValue(0.15)
        self.stretch_min.setValue(0.75)
        self.stretch_max.setValue(1.6)
        self.output_dir.setText("output")
        self.video_format.setCurrentText("mp4")
        self.subtitle_format.setCurrentText("srt")
        self.keep_audio_clips.setChecked(False)
        self.open_after_export.setChecked(True)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _dir_size_mb(path: str) -> float:
    """Return total size of *path* in megabytes (0.0 if missing)."""
    if not os.path.isdir(path):
        return 0.0
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for fname in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, fname))
            except OSError:
                pass
    return total / (1024 * 1024)


def _rmtree_contents(path: str) -> None:
    """Remove all files/subdirs inside *path* without deleting *path* itself."""
    if not os.path.isdir(path):
        return
    for entry in os.scandir(path):
        try:
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(entry.path)
            else:
                os.remove(entry.path)
        except OSError as exc:
            log.warning("Could not remove %s: %s", entry.path, exc)
