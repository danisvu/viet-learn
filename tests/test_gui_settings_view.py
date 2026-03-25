"""Tests for SettingsView — model selection, TTS, speed limits, output, storage.

PyQt6 runs offscreen — no display required.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.gui.views.settings_view import SettingsView, _dir_size_mb, _rmtree_contents


# ── Shared QApplication ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def view(qapp):
    v = SettingsView()
    yield v
    v.close()


# ---------------------------------------------------------------------------
# TestSettingsViewWidgets — all expected widgets exist
# ---------------------------------------------------------------------------

class TestSettingsViewWidgets:
    def test_has_ollama_url(self, view):
        assert hasattr(view, "ollama_url")

    def test_has_ollama_model(self, view):
        assert hasattr(view, "ollama_model")

    def test_has_whisper_model(self, view):
        assert hasattr(view, "whisper_model")

    def test_has_whisper_threads(self, view):
        assert hasattr(view, "whisper_threads")

    def test_has_tts_model(self, view):
        assert hasattr(view, "tts_model")

    def test_has_tts_speed(self, view):
        assert hasattr(view, "tts_speed")

    def test_has_original_vol(self, view):
        assert hasattr(view, "original_vol")

    def test_has_stretch_min(self, view):
        assert hasattr(view, "stretch_min")

    def test_has_stretch_max(self, view):
        assert hasattr(view, "stretch_max")

    def test_has_output_dir(self, view):
        assert hasattr(view, "output_dir")

    def test_has_video_format(self, view):
        assert hasattr(view, "video_format")

    def test_has_subtitle_format(self, view):
        assert hasattr(view, "subtitle_format")

    def test_has_keep_audio_clips(self, view):
        assert hasattr(view, "keep_audio_clips")

    def test_has_open_after_export(self, view):
        assert hasattr(view, "open_after_export")

    def test_has_refresh_usage_btn(self, view):
        assert hasattr(view, "refresh_usage_btn")

    def test_has_clear_cache_btn(self, view):
        assert hasattr(view, "clear_cache_btn")

    def test_has_clear_downloads_btn(self, view):
        assert hasattr(view, "clear_downloads_btn")

    def test_has_save_btn(self, view):
        assert hasattr(view, "save_btn")

    def test_has_reset_btn(self, view):
        assert hasattr(view, "reset_btn")


# ---------------------------------------------------------------------------
# TestModelSelectionDefaults
# ---------------------------------------------------------------------------

class TestModelSelectionDefaults:
    def test_ollama_url_default(self, view):
        assert view.ollama_url.text() == "http://localhost:11434"

    def test_ollama_model_default(self, view):
        assert view.ollama_model.currentText() == "qwen3:8b"

    def test_ollama_model_has_options(self, view):
        items = [view.ollama_model.itemText(i) for i in range(view.ollama_model.count())]
        assert "qwen3:8b" in items
        assert "qwen3:30b" in items

    def test_whisper_model_default(self, view):
        assert view.whisper_model.currentText() == "large-v3-turbo"

    def test_whisper_model_has_options(self, view):
        items = [view.whisper_model.itemText(i) for i in range(view.whisper_model.count())]
        assert "large-v3" in items
        assert "medium.en" in items

    def test_whisper_threads_default(self, view):
        assert view.whisper_threads.value() == 4

    def test_whisper_threads_range(self, view):
        assert view.whisper_threads.minimum() == 1
        assert view.whisper_threads.maximum() == 16


# ---------------------------------------------------------------------------
# TestTTSVoiceDefaults
# ---------------------------------------------------------------------------

class TestTTSVoiceDefaults:
    def test_tts_voice_default(self, view):
        assert view.tts_model.currentText() == "vi_VN-vais1000-medium"

    def test_tts_voice_has_high_option(self, view):
        items = [view.tts_model.itemText(i) for i in range(view.tts_model.count())]
        assert "vi_VN-vais1000-high" in items

    def test_tts_speed_default(self, view):
        assert view.tts_speed.value() == pytest.approx(1.0)

    def test_tts_speed_range(self, view):
        assert view.tts_speed.minimum() == pytest.approx(0.5)
        assert view.tts_speed.maximum() == pytest.approx(2.0)

    def test_tts_model_is_editable(self, view):
        assert view.tts_model.isEditable()


# ---------------------------------------------------------------------------
# TestSpeedLimits
# ---------------------------------------------------------------------------

class TestSpeedLimits:
    def test_stretch_min_default(self, view):
        assert view.stretch_min.value() == pytest.approx(0.75)

    def test_stretch_max_default(self, view):
        assert view.stretch_max.value() == pytest.approx(1.6)

    def test_stretch_min_range(self, view):
        assert view.stretch_min.minimum() == pytest.approx(0.5)
        assert view.stretch_min.maximum() == pytest.approx(1.0)

    def test_stretch_max_range(self, view):
        assert view.stretch_max.minimum() == pytest.approx(1.0)
        assert view.stretch_max.maximum() == pytest.approx(2.0)

    def test_original_vol_default(self, view):
        assert view.original_vol.value() == pytest.approx(0.15)

    def test_original_vol_range(self, view):
        assert view.original_vol.minimum() == pytest.approx(0.0)
        assert view.original_vol.maximum() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestOutputPreferences
# ---------------------------------------------------------------------------

class TestOutputPreferences:
    def test_output_dir_default(self, view):
        assert view.output_dir.text() == "output"

    def test_video_format_default(self, view):
        assert view.video_format.currentText() == "mp4"

    def test_video_format_options(self, view):
        items = [view.video_format.itemText(i) for i in range(view.video_format.count())]
        assert "mp4" in items
        assert "mkv" in items
        assert "webm" in items

    def test_subtitle_format_default(self, view):
        assert view.subtitle_format.currentText() == "srt"

    def test_subtitle_format_options(self, view):
        items = [view.subtitle_format.itemText(i) for i in range(view.subtitle_format.count())]
        assert "srt" in items
        assert "vtt" in items

    def test_keep_audio_clips_default_false(self, view):
        assert not view.keep_audio_clips.isChecked()

    def test_open_after_export_default_true(self, view):
        assert view.open_after_export.isChecked()

    def test_can_toggle_keep_audio_clips(self, view):
        view.keep_audio_clips.setChecked(True)
        assert view.keep_audio_clips.isChecked()
        view.keep_audio_clips.setChecked(False)

    def test_can_toggle_open_after_export(self, view):
        view.open_after_export.setChecked(False)
        assert not view.open_after_export.isChecked()
        view.open_after_export.setChecked(True)


# ---------------------------------------------------------------------------
# TestGetSettings
# ---------------------------------------------------------------------------

class TestGetSettings:
    def test_returns_dict(self, view):
        assert isinstance(view.get_settings(), dict)

    def test_ollama_section(self, view):
        s = view.get_settings()
        assert "ollama" in s
        assert s["ollama"]["base_url"] == "http://localhost:11434"
        assert s["ollama"]["model"] == "qwen3:8b"

    def test_whisper_section(self, view):
        s = view.get_settings()
        assert "whisper" in s
        assert s["whisper"]["model"] == "large-v3-turbo"
        assert s["whisper"]["n_threads"] == 4

    def test_tts_section(self, view):
        s = view.get_settings()
        assert "tts" in s
        assert s["tts"]["speed"] == pytest.approx(1.0)

    def test_time_stretch_section(self, view):
        s = view.get_settings()
        assert "time_stretch" in s
        assert s["time_stretch"]["min_speed_ratio"] == pytest.approx(0.75)
        assert s["time_stretch"]["max_speed_ratio"] == pytest.approx(1.6)

    def test_output_section(self, view):
        s = view.get_settings()
        assert "output" in s
        assert s["output"]["directory"] == "output"
        assert s["output"]["video_format"] == "mp4"
        assert s["output"]["subtitle_format"] == "srt"
        assert s["output"]["keep_audio_clips"] is False
        assert s["output"]["open_after_export"] is True

    def test_settings_reflect_changes(self, view):
        view.tts_speed.setValue(1.3)
        view.stretch_min.setValue(0.8)
        s = view.get_settings()
        assert s["tts"]["speed"] == pytest.approx(1.3)
        assert s["time_stretch"]["min_speed_ratio"] == pytest.approx(0.8)
        # restore
        view.tts_speed.setValue(1.0)
        view.stretch_min.setValue(0.75)


# ---------------------------------------------------------------------------
# TestResetDefaults
# ---------------------------------------------------------------------------

class TestResetDefaults:
    def test_reset_restores_ollama_url(self, view):
        view.ollama_url.setText("http://192.168.1.10:11434")
        view.reset_btn.click()
        assert view.ollama_url.text() == "http://localhost:11434"

    def test_reset_restores_tts_speed(self, view):
        view.tts_speed.setValue(1.8)
        view.reset_btn.click()
        assert view.tts_speed.value() == pytest.approx(1.0)

    def test_reset_restores_stretch_min(self, view):
        view.stretch_min.setValue(0.6)
        view.reset_btn.click()
        assert view.stretch_min.value() == pytest.approx(0.75)

    def test_reset_restores_stretch_max(self, view):
        view.stretch_max.setValue(2.0)
        view.reset_btn.click()
        assert view.stretch_max.value() == pytest.approx(1.6)

    def test_reset_restores_output_dir(self, view):
        view.output_dir.setText("/tmp/custom")
        view.reset_btn.click()
        assert view.output_dir.text() == "output"

    def test_reset_restores_keep_audio_clips(self, view):
        view.keep_audio_clips.setChecked(True)
        view.reset_btn.click()
        assert not view.keep_audio_clips.isChecked()

    def test_reset_restores_open_after_export(self, view):
        view.open_after_export.setChecked(False)
        view.reset_btn.click()
        assert view.open_after_export.isChecked()

    def test_reset_restores_whisper_threads(self, view):
        view.whisper_threads.setValue(8)
        view.reset_btn.click()
        assert view.whisper_threads.value() == 4


# ---------------------------------------------------------------------------
# TestStorageLabels
# ---------------------------------------------------------------------------

class TestStorageLabels:
    def test_usage_label_exists(self, view):
        assert hasattr(view, "_usage_label")

    def test_usage_label_has_text_after_init(self, view):
        # After __init__ refresh_storage_usage() is called — label is not empty
        assert view._usage_label.text() != ""

    def test_cache_label_has_text(self, view):
        assert view._cache_label.text() != ""

    def test_dl_label_has_text(self, view):
        assert view._dl_label.text() != ""

    def test_refresh_button_updates_labels(self, view, qapp):
        view.output_dir.setText("output")
        view.refresh_usage_btn.click()
        qapp.processEvents()
        # Label should contain 'MB'
        assert "MB" in view._usage_label.text()

    def test_usage_shows_mb_suffix(self, view):
        view.refresh_storage_usage()
        assert view._usage_label.text().endswith("MB")

    def test_cache_shows_mb_suffix(self, view):
        view.refresh_storage_usage()
        assert view._cache_label.text().endswith("MB")

    def test_dl_shows_mb_suffix(self, view):
        view.refresh_storage_usage()
        assert view._dl_label.text().endswith("MB")


# ---------------------------------------------------------------------------
# TestDirSizeMb — helper function
# ---------------------------------------------------------------------------

class TestDirSizeMb:
    def test_missing_dir_returns_zero(self, tmp_path):
        assert _dir_size_mb(str(tmp_path / "nonexistent")) == 0.0

    def test_empty_dir_returns_zero(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert _dir_size_mb(str(d)) == pytest.approx(0.0)

    def test_single_file_size(self, tmp_path):
        f = tmp_path / "file.bin"
        f.write_bytes(b"x" * 1024 * 1024)  # 1 MB
        result = _dir_size_mb(str(tmp_path))
        assert result == pytest.approx(1.0, abs=0.01)

    def test_nested_files_summed(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "a.bin").write_bytes(b"x" * 512 * 1024)   # 0.5 MB
        (sub / "b.bin").write_bytes(b"x" * 512 * 1024)         # 0.5 MB
        assert _dir_size_mb(str(tmp_path)) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# TestRmtreeContents — helper function
# ---------------------------------------------------------------------------

class TestRmtreeContents:
    def test_missing_dir_does_not_raise(self, tmp_path):
        _rmtree_contents(str(tmp_path / "ghost"))  # should not raise

    def test_removes_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("hi")
        (tmp_path / "b.txt").write_text("there")
        _rmtree_contents(str(tmp_path))
        assert list(tmp_path.iterdir()) == []

    def test_removes_subdirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("data")
        _rmtree_contents(str(tmp_path))
        assert not sub.exists()

    def test_keeps_root_dir(self, tmp_path):
        (tmp_path / "x.txt").write_text("x")
        _rmtree_contents(str(tmp_path))
        assert tmp_path.exists()


# ---------------------------------------------------------------------------
# TestClearCache / TestClearDownloads
# ---------------------------------------------------------------------------

class TestClearCache:
    def test_clear_cache_removes_stt_contents(self, view, tmp_path):
        stt_dir = tmp_path / "stt"
        stt_dir.mkdir()
        (stt_dir / "audio.wav").write_bytes(b"\x00" * 100)

        view.output_dir.setText(str(tmp_path))
        view._clear_cache()
        assert list(stt_dir.iterdir()) == []

    def test_clear_cache_updates_labels(self, view, tmp_path, qapp):
        view.output_dir.setText(str(tmp_path))
        view._clear_cache()
        qapp.processEvents()
        assert "MB" in view._cache_label.text()

    def test_clear_cache_nonexistent_dir_does_not_raise(self, view, tmp_path):
        view.output_dir.setText(str(tmp_path / "ghost"))
        view._clear_cache()  # should not raise


class TestClearDownloads:
    def test_clear_downloads_removes_files(self, view, tmp_path):
        dl_dir = tmp_path / "downloads"
        dl_dir.mkdir()
        (dl_dir / "video.mp4").write_bytes(b"\x00" * 200)

        view.output_dir.setText(str(tmp_path))
        view._clear_downloads()
        assert list(dl_dir.iterdir()) == []

    def test_clear_downloads_updates_labels(self, view, tmp_path, qapp):
        view.output_dir.setText(str(tmp_path))
        view._clear_downloads()
        qapp.processEvents()
        assert "MB" in view._dl_label.text()

    def test_clear_downloads_nonexistent_dir_does_not_raise(self, view, tmp_path):
        view.output_dir.setText(str(tmp_path / "ghost"))
        view._clear_downloads()  # should not raise
