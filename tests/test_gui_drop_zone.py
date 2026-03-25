"""Tests for FileDropZone widget and validate_drop_paths helper.

PyQt6 runs in offscreen mode — no display required.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication

from src.gui.views._drop_zone import (
    FileDropZone,
    _ACCEPTED_EXTS,
    _SUBTITLE_EXTS,
    _VIDEO_EXTS,
    validate_drop_paths,
)


# ── Shared QApplication ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def zone(qapp):
    w = FileDropZone()
    yield w
    w.close()


# ---------------------------------------------------------------------------
# TestExtSets — verify the extension constants are correct
# ---------------------------------------------------------------------------

class TestExtSets:
    def test_video_exts_contains_mp4(self):
        assert ".mp4" in _VIDEO_EXTS

    def test_video_exts_contains_webm(self):
        assert ".webm" in _VIDEO_EXTS

    def test_video_exts_contains_mkv(self):
        assert ".mkv" in _VIDEO_EXTS

    def test_subtitle_exts_contains_srt(self):
        assert ".srt" in _SUBTITLE_EXTS

    def test_subtitle_exts_contains_vtt(self):
        assert ".vtt" in _SUBTITLE_EXTS

    def test_accepted_is_union(self):
        assert _ACCEPTED_EXTS == _VIDEO_EXTS | _SUBTITLE_EXTS


# ---------------------------------------------------------------------------
# TestClassifyFile — static helper
# ---------------------------------------------------------------------------

class TestClassifyFile:
    def test_mp4_is_video(self):
        assert FileDropZone.classify_file("/path/to/lecture.mp4") == "video"

    def test_webm_is_video(self):
        assert FileDropZone.classify_file("/path/to/lecture.webm") == "video"

    def test_mkv_is_video(self):
        assert FileDropZone.classify_file("/path/to/lecture.mkv") == "video"

    def test_srt_is_subtitle(self):
        assert FileDropZone.classify_file("/path/to/lecture.srt") == "subtitle"

    def test_vtt_is_subtitle(self):
        assert FileDropZone.classify_file("/path/to/lecture.vtt") == "subtitle"

    def test_unknown_ext_returns_empty(self):
        assert FileDropZone.classify_file("/path/to/file.pdf") == ""

    def test_no_ext_returns_empty(self):
        assert FileDropZone.classify_file("/path/to/file") == ""

    def test_uppercase_ext_normalised(self):
        assert FileDropZone.classify_file("/path/to/LECTURE.MP4") == "video"

    def test_mixed_case_srt(self):
        assert FileDropZone.classify_file("/path/to/LECTURE.SRT") == "subtitle"


# ---------------------------------------------------------------------------
# TestValidateDropPaths — pure logic, no Qt events
# ---------------------------------------------------------------------------

class TestValidateDropPaths:
    def test_single_video_valid(self):
        videos, subs, err = validate_drop_paths(["/a/b.mp4"])
        assert videos == ["/a/b.mp4"]
        assert subs == []
        assert err == ""

    def test_single_subtitle_valid(self):
        videos, subs, err = validate_drop_paths(["/a/b.srt"])
        assert videos == []
        assert subs == ["/a/b.srt"]
        assert err == ""

    def test_video_and_subtitle_together_valid(self):
        videos, subs, err = validate_drop_paths(["/a/b.mp4", "/a/b.srt"])
        assert videos == ["/a/b.mp4"]
        assert subs == ["/a/b.srt"]
        assert err == ""

    def test_two_videos_returns_error(self):
        _, _, err = validate_drop_paths(["/a/a.mp4", "/b/b.mkv"])
        assert err != ""
        assert "video" in err.lower()

    def test_two_subtitles_returns_error(self):
        _, _, err = validate_drop_paths(["/a/a.srt", "/b/b.vtt"])
        assert err != ""
        assert "subtitle" in err.lower()

    def test_unknown_ext_returns_error(self):
        _, _, err = validate_drop_paths(["/a/doc.pdf"])
        assert err != ""
        assert ".pdf" in err

    def test_mixed_valid_and_unknown_returns_error(self):
        _, _, err = validate_drop_paths(["/a/b.mp4", "/a/c.docx"])
        assert err != ""

    def test_empty_list_valid(self):
        videos, subs, err = validate_drop_paths([])
        assert videos == []
        assert subs == []
        assert err == ""

    def test_two_videos_lists_are_empty_on_error(self):
        videos, subs, err = validate_drop_paths(["/a/a.mp4", "/b/b.mp4"])
        assert videos == []
        assert subs == []

    def test_unknown_ext_no_dot(self):
        """File without extension triggers unsupported error."""
        _, _, err = validate_drop_paths(["/a/noextfile"])
        assert err != ""

    def test_webm_and_vtt_valid(self):
        videos, subs, err = validate_drop_paths(["/a/v.webm", "/a/s.vtt"])
        assert err == ""
        assert videos == ["/a/v.webm"]
        assert subs == ["/a/s.vtt"]


# ---------------------------------------------------------------------------
# TestFileDropZoneWidget — widget-level tests
# ---------------------------------------------------------------------------

class TestFileDropZoneWidget:
    def test_widget_created(self, zone):
        assert zone is not None

    def test_accepts_drops_enabled(self, zone):
        assert zone.acceptDrops() is True

    def test_has_hint_label(self, zone):
        assert hasattr(zone, "_hint_label")

    def test_has_icon_label(self, zone):
        assert hasattr(zone, "_icon_label")

    def test_minimum_height(self, zone):
        assert zone.minimumHeight() >= 100

    def test_has_video_dropped_signal(self, zone):
        assert hasattr(zone, "video_dropped")

    def test_has_subtitle_dropped_signal(self, zone):
        assert hasattr(zone, "subtitle_dropped")

    def test_has_error_signal(self, zone):
        assert hasattr(zone, "error")

    def test_classify_file_accessible_on_instance(self, zone):
        assert zone.classify_file("/foo/bar.mp4") == "video"


# ---------------------------------------------------------------------------
# TestFileDropZoneSignals — signal emission via _show_error / simulate drops
# ---------------------------------------------------------------------------

def _make_mime_data(file_paths: list[str]) -> QMimeData:
    """Build a QMimeData with local file URLs."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in file_paths])
    return mime


class TestFileDropZoneSignals:
    def test_error_signal_emitted_on_two_videos(self, zone, qapp):
        received: list[str] = []
        zone.error.connect(received.append)
        mime = _make_mime_data(["/a/a.mp4", "/b/b.mkv"])

        # Simulate the drop by calling dropEvent logic through _show_error path
        # We call the internal validation directly and fire the signal
        from src.gui.views._drop_zone import validate_drop_paths
        _, _, err = validate_drop_paths(["/a/a.mp4", "/b/b.mkv"])
        zone._show_error(err)
        qapp.processEvents()

        assert len(received) == 1
        assert "video" in received[0].lower()

    def test_error_signal_emitted_on_unknown_ext(self, zone, qapp):
        received: list[str] = []
        zone.error.connect(received.append)
        from src.gui.views._drop_zone import validate_drop_paths
        _, _, err = validate_drop_paths(["/a/file.pdf"])
        zone._show_error(err)
        qapp.processEvents()

        assert len(received) == 1
        assert ".pdf" in received[0]

    def test_video_dropped_signal(self, zone, qapp):
        received: list[str] = []
        zone.video_dropped.connect(received.append)
        zone.video_dropped.emit("/a/video.mp4")
        qapp.processEvents()
        assert received == ["/a/video.mp4"]

    def test_subtitle_dropped_signal(self, zone, qapp):
        received: list[str] = []
        zone.subtitle_dropped.connect(received.append)
        zone.subtitle_dropped.emit("/a/subs.srt")
        qapp.processEvents()
        assert received == ["/a/subs.srt"]

    def test_reset_style_restores_idle(self, zone):
        from src.gui.views._drop_zone import _STYLE_IDLE, _STYLE_ERROR
        zone._show_error("test")
        zone._reset_style()
        assert zone.styleSheet() == _STYLE_IDLE

    def test_show_error_changes_style(self, zone):
        from src.gui.views._drop_zone import _STYLE_ERROR
        zone._show_error("some error")
        assert zone.styleSheet() == _STYLE_ERROR


# ---------------------------------------------------------------------------
# TestDLAIViewDropIntegration — DLAIView wires drop zone to path fields
# ---------------------------------------------------------------------------

class TestDLAIViewDropIntegration:
    @pytest.fixture
    def dlai(self, qapp):
        from src.gui.views.dlai_view import DLAIView
        v = DLAIView()
        yield v
        v.close()

    def test_has_drop_zone(self, dlai):
        assert hasattr(dlai, "drop_zone")
        assert isinstance(dlai.drop_zone, FileDropZone)

    def test_video_drop_populates_video_path(self, dlai, qapp):
        dlai.drop_zone.video_dropped.emit("/tmp/lecture.mp4")
        qapp.processEvents()
        assert dlai.video_path.text() == "/tmp/lecture.mp4"

    def test_subtitle_drop_populates_sub_path(self, dlai, qapp):
        dlai.drop_zone.subtitle_dropped.emit("/tmp/lecture.srt")
        qapp.processEvents()
        assert dlai.sub_path.text() == "/tmp/lecture.srt"

    def test_drop_error_shows_in_status_label(self, dlai, qapp):
        dlai.drop_zone.error.emit("Unsupported file type: .pdf")
        qapp.processEvents()
        assert "Unsupported" in dlai.status_label.text()

    def test_valid_drop_clears_status_label(self, dlai, qapp):
        # First set an error, then a valid drop should clear it
        dlai.status_label.setText("some old error")
        dlai.drop_zone.video_dropped.emit("/tmp/lecture.mp4")
        qapp.processEvents()
        assert dlai.status_label.text() == ""
