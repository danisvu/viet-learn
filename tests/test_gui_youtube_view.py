"""Tests for YouTubeView, QueueEntry, ItemStatus, and detect_url_type.

PyQt6 runs in offscreen mode — no display required.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from src.gui.views._badge import detect_url_type
from src.gui.views._download_panel import (
    ActiveDownloadPanel,
    SubtitlePreviewPanel,
    _format_eta,
    _format_speed,
)
from src.gui.views._worker import ItemStatus, QueueEntry, _DownloadWorker
from src.gui.views.youtube_view import YouTubeView


# ── Shared QApplication ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def view(qapp):
    v = YouTubeView()
    yield v
    v.close()


# ---------------------------------------------------------------------------
# TestDetectUrlType
# ---------------------------------------------------------------------------

class TestDetectUrlType:
    def test_empty_string(self):
        assert detect_url_type("") == ("", False)

    def test_whitespace_only(self):
        assert detect_url_type("   ") == ("", False)

    def test_plain_video_watch_url(self):
        badge, is_pl = detect_url_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert badge == "Video"
        assert is_pl is False

    def test_short_youtu_be_url(self):
        badge, is_pl = detect_url_type("https://youtu.be/dQw4w9WgXcQ")
        assert badge == "Video"
        assert is_pl is False

    def test_v_param_without_domain(self):
        badge, is_pl = detect_url_type("https://example.com/?v=abc")
        assert badge == "Video"
        assert is_pl is False

    def test_playlist_with_list_param(self):
        badge, is_pl = detect_url_type(
            "https://www.youtube.com/playlist?list=PLxyz"
        )
        assert badge == "Playlist"
        assert is_pl is True

    def test_video_url_with_list_param_is_playlist(self):
        # A watch URL that also has list= is treated as playlist
        badge, is_pl = detect_url_type(
            "https://www.youtube.com/watch?v=abc&list=PLxyz"
        )
        assert badge == "Playlist"
        assert is_pl is True

    def test_youtube_com_playlist_path(self):
        badge, is_pl = detect_url_type(
            "https://www.youtube.com/playlist?list=PLxyz"
        )
        assert badge == "Playlist"
        assert is_pl is True

    def test_unrecognised_url(self):
        badge, is_pl = detect_url_type("https://example.com/video")
        assert badge == ""
        assert is_pl is False

    def test_strips_leading_trailing_whitespace(self):
        badge, _ = detect_url_type("  https://youtu.be/abc  ")
        assert badge == "Video"

    def test_returns_tuple(self):
        result = detect_url_type("https://youtu.be/abc")
        assert isinstance(result, tuple)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestItemStatus
# ---------------------------------------------------------------------------

class TestItemStatus:
    def test_pending_label(self):
        assert ItemStatus.PENDING.label() == "Pending"

    def test_downloading_label(self):
        assert ItemStatus.DOWNLOADING.label() == "Downloading…"

    def test_done_label(self):
        assert ItemStatus.DONE.label() == "Done"

    def test_error_label(self):
        assert ItemStatus.ERROR.label() == "Error"

    def test_all_statuses_have_labels(self):
        for status in ItemStatus:
            assert isinstance(status.label(), str)
            assert len(status.label()) > 0


# ---------------------------------------------------------------------------
# TestQueueEntry
# ---------------------------------------------------------------------------

class TestQueueEntry:
    def test_default_status_is_pending(self):
        e = QueueEntry(url="https://youtu.be/x", badge="Video", is_playlist=False)
        assert e.status == ItemStatus.PENDING

    def test_default_progress_empty(self):
        e = QueueEntry(url="https://youtu.be/x", badge="Video", is_playlist=False)
        assert e.progress == ""

    def test_default_title_empty(self):
        e = QueueEntry(url="https://youtu.be/x", badge="Video", is_playlist=False)
        assert e.title == ""

    def test_stores_url(self):
        url = "https://youtu.be/abc"
        e = QueueEntry(url=url, badge="Video", is_playlist=False)
        assert e.url == url

    def test_stores_badge(self):
        e = QueueEntry(url="u", badge="Playlist", is_playlist=True)
        assert e.badge == "Playlist"

    def test_stores_is_playlist(self):
        e = QueueEntry(url="u", badge="Playlist", is_playlist=True)
        assert e.is_playlist is True


# ---------------------------------------------------------------------------
# TestYouTubeViewWidgets
# ---------------------------------------------------------------------------

class TestYouTubeViewWidgets:
    def test_has_url_input(self, view):
        assert hasattr(view, "url_input")

    def test_has_add_btn(self, view):
        assert hasattr(view, "add_btn")

    def test_has_queue_table(self, view):
        assert hasattr(view, "queue_table")

    def test_has_download_btn(self, view):
        assert hasattr(view, "download_btn")

    def test_has_remove_btn(self, view):
        assert hasattr(view, "remove_btn")

    def test_has_clear_done_btn(self, view):
        assert hasattr(view, "clear_done_btn")

    def test_queue_table_has_four_columns(self, view):
        assert view.queue_table.columnCount() == 4

    def test_queue_table_column_headers(self, view):
        headers = [
            view.queue_table.horizontalHeaderItem(i).text()
            for i in range(view.queue_table.columnCount())
        ]
        assert headers == ["Title / URL", "Type", "Status", "Progress"]

    def test_remove_btn_disabled_initially(self, view):
        assert not view.remove_btn.isEnabled()

    def test_queue_initially_empty(self, view):
        assert view.queue_size() == 0
        assert view.queue_table.rowCount() == 0


# ---------------------------------------------------------------------------
# TestYouTubeViewAddUrl
# ---------------------------------------------------------------------------

class TestYouTubeViewAddUrl:
    def test_add_video_url(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_size() == 1

    def test_add_inserts_table_row(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_table.rowCount() == 1

    def test_add_clears_url_input(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.url_input.text() == ""

    def test_add_duplicate_url_not_added_twice(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_size() == 1

    def test_add_empty_url_does_nothing(self, view):
        view.url_input.setText("")
        view._add_url()
        assert view.queue_size() == 0

    def test_add_whitespace_url_does_nothing(self, view):
        view.url_input.setText("   ")
        view._add_url()
        assert view.queue_size() == 0

    def test_entry_has_correct_badge_video(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        entry = view.entry("https://youtu.be/abc")
        assert entry is not None
        assert entry.badge == "Video"
        assert entry.is_playlist is False

    def test_entry_has_correct_badge_playlist(self, view):
        url = "https://www.youtube.com/playlist?list=PLxyz"
        view.url_input.setText(url)
        view._add_url()
        entry = view.entry(url)
        assert entry is not None
        assert entry.badge == "Playlist"
        assert entry.is_playlist is True

    def test_entry_starts_as_pending(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        entry = view.entry("https://youtu.be/abc")
        assert entry.status == ItemStatus.PENDING

    def test_table_row_shows_url(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_table.item(0, 0).text() == "https://youtu.be/abc"

    def test_table_row_shows_badge(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_table.item(0, 1).text() == "Video"

    def test_table_row_shows_pending_status(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        assert view.queue_table.item(0, 2).text() == "Pending"

    def test_add_multiple_urls(self, view):
        view.url_input.setText("https://youtu.be/aaa")
        view._add_url()
        view.url_input.setText("https://youtu.be/bbb")
        view._add_url()
        assert view.queue_size() == 2
        assert view.queue_table.rowCount() == 2

    def test_return_pressed_adds_url(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view.url_input.returnPressed.emit()
        assert view.queue_size() == 1


# ---------------------------------------------------------------------------
# TestYouTubeViewBadgeLive
# ---------------------------------------------------------------------------

class TestYouTubeViewBadgeLive:
    def test_badge_label_updates_on_text_change_video(self, view):
        view.url_input.setText("https://youtu.be/abc")
        assert view._badge_label.text() == "Video"

    def test_badge_label_updates_on_text_change_playlist(self, view):
        view.url_input.setText("https://www.youtube.com/playlist?list=PLx")
        assert view._badge_label.text() == "Playlist"

    def test_badge_label_clears_on_empty(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view.url_input.clear()
        assert view._badge_label.text() == ""


# ---------------------------------------------------------------------------
# TestYouTubeViewClearDone
# ---------------------------------------------------------------------------

class TestYouTubeViewClearDone:
    def _add(self, view, url):
        view.url_input.setText(url)
        view._add_url()

    def test_clear_done_removes_done_entries(self, view):
        self._add(view, "https://youtu.be/aaa")
        entry = view.entry("https://youtu.be/aaa")
        entry.status = ItemStatus.DONE
        view._clear_done()
        assert view.queue_size() == 0

    def test_clear_done_keeps_pending_entries(self, view):
        self._add(view, "https://youtu.be/aaa")
        self._add(view, "https://youtu.be/bbb")
        view.entry("https://youtu.be/aaa").status = ItemStatus.DONE
        view._clear_done()
        assert view.queue_size() == 1
        assert "https://youtu.be/bbb" in view._entries

    def test_clear_done_removes_table_rows(self, view):
        self._add(view, "https://youtu.be/aaa")
        view.entry("https://youtu.be/aaa").status = ItemStatus.DONE
        view._clear_done()
        assert view.queue_table.rowCount() == 0


# ---------------------------------------------------------------------------
# TestYouTubeViewDownloadButton
# ---------------------------------------------------------------------------

class TestYouTubeViewDownloadButton:
    def test_download_btn_enabled_by_default(self, view):
        # No worker running; button starts enabled
        assert view.download_btn.isEnabled()

    def test_start_download_without_factory_does_nothing(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()
        view._start_download()  # factory is None — must not crash
        assert view.queue_size() == 1


# ---------------------------------------------------------------------------
# TestDownloadWorkerSignals
# ---------------------------------------------------------------------------

class TestDownloadWorkerSignals:
    def _run_worker(self, worker, qapp):
        """Start worker, wait for it to finish, then flush queued signals."""
        worker.start()
        worker.wait(5000)
        qapp.processEvents()

    def test_worker_emits_item_done_on_success(self, qapp):
        results_received = []
        url = "https://youtu.be/abc"
        fake_results = [object()]

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    return fake_results
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.item_done.connect(lambda u, r: results_received.append((u, r)))
        self._run_worker(worker, qapp)
        assert len(results_received) == 1
        assert results_received[0][0] == url
        assert results_received[0][1] == fake_results

    def test_worker_emits_item_error_on_exception(self, qapp):
        errors_received = []
        url = "https://youtu.be/abc"

        def factory():
            class BrokenDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    raise RuntimeError("network error")
            return BrokenDownloader()

        worker = _DownloadWorker([url], factory)
        worker.item_error.connect(lambda u, e: errors_received.append((u, e)))
        self._run_worker(worker, qapp)
        assert len(errors_received) == 1
        assert errors_received[0][0] == url
        assert "network error" in errors_received[0][1]

    def test_worker_emits_progress_signal(self, qapp):
        progress_received = []
        url = "https://youtu.be/abc"

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    if progress_callback:
                        progress_callback(1, 1, "Test Video")
                    return []
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.progress.connect(lambda u, c, t, title: progress_received.append((u, c, t, title)))
        self._run_worker(worker, qapp)
        assert len(progress_received) == 1
        assert progress_received[0] == (url, 1, 1, "Test Video")

    def test_worker_processes_multiple_urls(self, qapp):
        done_urls = []
        urls = ["https://youtu.be/a", "https://youtu.be/b", "https://youtu.be/c"]

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    return []
            return FakeDownloader()

        worker = _DownloadWorker(urls, factory)
        worker.item_done.connect(lambda u, r: done_urls.append(u))
        self._run_worker(worker, qapp)
        assert sorted(done_urls) == sorted(urls)

    def test_worker_accepts_ytdlp_hooks(self, qapp):
        """Worker passes ytdlp_hooks to downloader.download()."""
        hooks_received = []
        url = "https://youtu.be/abc"

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    if ytdlp_hooks:
                        hooks_received.extend(ytdlp_hooks)
                    return []
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        self._run_worker(worker, qapp)
        assert len(hooks_received) == 1
        assert callable(hooks_received[0])

    def test_worker_emits_step_changed(self, qapp):
        steps = []
        url = "https://youtu.be/abc"

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    return []
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.step_changed.connect(lambda u, s: steps.append(s))
        self._run_worker(worker, qapp)
        assert len(steps) >= 2  # at least "Fetching info…" + "Complete ✓"
        assert any("Fetching" in s for s in steps)
        assert any("Complete" in s for s in steps)

    def test_worker_emits_byte_progress_from_hook(self, qapp):
        byte_signals = []
        url = "https://youtu.be/abc"

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    if ytdlp_hooks:
                        ytdlp_hooks[0]({
                            "status": "downloading",
                            "downloaded_bytes": 512,
                            "total_bytes": 1024,
                            "eta": 5,
                            "speed": 102400.0,
                        })
                    return []
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.byte_progress.connect(lambda u, d, t, e, s: byte_signals.append((d, t, e, s)))
        self._run_worker(worker, qapp)
        assert len(byte_signals) == 1
        assert byte_signals[0] == (512, 1024, 5, 102400.0)

    def test_worker_emits_merging_step_on_hook_finished(self, qapp):
        steps = []
        url = "https://youtu.be/abc"

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    if ytdlp_hooks:
                        ytdlp_hooks[0]({"status": "finished"})
                    return []
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.step_changed.connect(lambda u, s: steps.append(s))
        self._run_worker(worker, qapp)
        assert any("Merging" in s for s in steps)

    def test_worker_emits_subtitle_preview(self, qapp, tmp_path):
        previews = []
        url = "https://youtu.be/abc"
        srt = tmp_path / "sub.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nHello world.\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond line.\n",
            encoding="utf-8",
        )

        def factory():
            class FakeResult:
                subtitle_path = str(srt)

            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    return [FakeResult()]
            return FakeDownloader()

        worker = _DownloadWorker([url], factory)
        worker.subtitle_preview.connect(lambda u, t: previews.append(t))
        self._run_worker(worker, qapp)
        assert len(previews) == 1
        assert "Hello world." in previews[0]


# ---------------------------------------------------------------------------
# TestReadSubtitlePreview
# ---------------------------------------------------------------------------

class TestReadSubtitlePreview:
    def test_returns_first_three_blocks(self, tmp_path):
        srt = tmp_path / "sub.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nLine one.\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nLine two.\n\n"
            "3\n00:00:05,000 --> 00:00:06,000\nLine three.\n\n"
            "4\n00:00:07,000 --> 00:00:08,000\nLine four.\n",
            encoding="utf-8",
        )
        result = _DownloadWorker._read_subtitle_preview(str(srt))
        assert "Line one." in result
        assert "Line three." in result
        assert "Line four." not in result

    def test_missing_file_returns_empty(self):
        result = _DownloadWorker._read_subtitle_preview("/nonexistent/file.srt")
        assert result == ""

    def test_custom_max_entries(self, tmp_path):
        srt = tmp_path / "sub.srt"
        srt.write_text(
            "1\n00:00:01,000 --> 00:00:02,000\nA.\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nB.\n",
            encoding="utf-8",
        )
        result = _DownloadWorker._read_subtitle_preview(str(srt), max_entries=1)
        assert "A." in result
        assert "B." not in result


# ---------------------------------------------------------------------------
# TestFormatEta
# ---------------------------------------------------------------------------

class TestFormatEta:
    def test_zero_returns_dash(self):
        assert _format_eta(0) == "–"

    def test_negative_returns_dash(self):
        assert _format_eta(-5) == "–"

    def test_seconds_only(self):
        assert _format_eta(45) == "45s"

    def test_minutes_and_seconds(self):
        assert _format_eta(90) == "1m 30s"

    def test_exact_minute(self):
        assert _format_eta(60) == "1m 00s"

    def test_large_value(self):
        result = _format_eta(3661)
        assert "61m" in result or "1h" in result or "61" in result


# ---------------------------------------------------------------------------
# TestFormatSpeed
# ---------------------------------------------------------------------------

class TestFormatSpeed:
    def test_zero_returns_empty(self):
        assert _format_speed(0) == ""

    def test_negative_returns_empty(self):
        assert _format_speed(-1) == ""

    def test_kilobytes(self):
        result = _format_speed(50 * 1024)
        assert "KB/s" in result

    def test_megabytes(self):
        result = _format_speed(2.5 * 1024 * 1024)
        assert "MB/s" in result
        assert "2.5" in result

    def test_threshold_between_kb_mb(self):
        # Just below 0.1 MB → KB/s
        result_low = _format_speed(0.09 * 1024 * 1024)
        assert "KB/s" in result_low
        # At 0.1 MB → MB/s
        result_high = _format_speed(0.1 * 1024 * 1024)
        assert "MB/s" in result_high


# ---------------------------------------------------------------------------
# TestActiveDownloadPanel
# ---------------------------------------------------------------------------

class TestActiveDownloadPanel:
    @pytest.fixture
    def panel(self, qapp):
        p = ActiveDownloadPanel()
        yield p
        p.close()

    def test_initial_step_text(self, panel):
        assert panel.step_text == "Waiting…"

    def test_initial_bar_value_zero(self, panel):
        assert panel.bar_value == 0

    def test_initial_eta_empty(self, panel):
        assert panel.eta_text == ""

    def test_update_step(self, panel):
        panel.update_step("1/3 — Downloading")
        assert panel.step_text == "1/3 — Downloading"

    def test_update_byte_progress_sets_percentage(self, panel):
        panel.update_byte_progress(512, 1024, 10, 102400.0)
        assert panel.bar_value == 50

    def test_update_byte_progress_shows_eta(self, panel):
        panel.update_byte_progress(512, 1024, 30, 0.0)
        assert "ETA" in panel.eta_text
        assert "30s" in panel.eta_text

    def test_update_byte_progress_shows_speed(self, panel):
        panel.update_byte_progress(0, 0, 0, 2.5 * 1024 * 1024)
        assert "MB/s" in panel.eta_text

    def test_update_byte_progress_zero_total_is_indeterminate(self, panel):
        panel.update_byte_progress(0, 0, 0, 0.0)
        assert panel.bar_maximum == 0  # indeterminate

    def test_set_complete_snaps_to_100(self, panel):
        panel.update_byte_progress(512, 1024, 10, 0.0)
        panel.set_complete()
        assert panel.bar_value == 100
        assert panel.eta_text == ""

    def test_set_indeterminate(self, panel):
        panel.set_indeterminate()
        assert panel.bar_maximum == 0

    def test_reset_restores_defaults(self, panel):
        panel.update_step("Downloading…")
        panel.update_byte_progress(512, 1024, 10, 0.0)
        panel.reset()
        assert panel.bar_value == 0
        assert panel.bar_maximum == 100
        assert panel.eta_text == ""


# ---------------------------------------------------------------------------
# TestSubtitlePreviewPanel
# ---------------------------------------------------------------------------

class TestSubtitlePreviewPanel:
    @pytest.fixture
    def panel(self, qapp):
        p = SubtitlePreviewPanel()
        yield p
        p.close()

    def test_initial_preview_empty(self, panel):
        assert panel.preview_text == ""

    def test_show_preview_sets_text(self, panel):
        panel.show_preview("1\n00:00:01,000 --> 00:00:02,000\nHello.")
        assert "Hello." in panel.preview_text

    def test_show_preview_truncates_long_text(self, panel):
        long_text = "x" * 1000
        panel.show_preview(long_text)
        assert len(panel.preview_text) <= 800

    def test_clear_removes_text(self, panel):
        panel.show_preview("Some text")
        panel.clear()
        assert panel.preview_text == ""


# ---------------------------------------------------------------------------
# TestYouTubeViewPanels
# ---------------------------------------------------------------------------

class TestYouTubeViewPanels:
    @pytest.fixture
    def view(self, qapp):
        v = YouTubeView()
        yield v
        v.close()

    def test_active_panel_hidden_initially(self, view):
        assert not view._active_panel.isVisible()

    def test_subtitle_panel_hidden_initially(self, view):
        assert not view._subtitle_panel.isVisible()

    def test_active_panel_shown_when_download_starts(self, view):
        view.url_input.setText("https://youtu.be/abc")
        view._add_url()

        def factory():
            class FakeDownloader:
                def download(self, u, progress_callback=None, ytdlp_hooks=None):
                    return []
            return FakeDownloader()

        view._downloader_factory = factory
        view._start_download()
        assert not view._active_panel.isHidden()

    def test_step_signal_updates_panel(self, view):
        view._on_step_changed("https://youtu.be/abc", "2/3 — Downloading")
        assert view._active_panel.step_text == "2/3 — Downloading"

    def test_byte_progress_signal_updates_panel(self, view):
        view._on_byte_progress("https://youtu.be/abc", 256, 1024, 15, 0.0)
        assert view._active_panel.bar_value == 25

    def test_subtitle_preview_signal_shows_panel(self, view):
        view._on_subtitle_preview("https://youtu.be/abc", "1\n00:00:01,000 --> 00:00:02,000\nHi.")
        assert not view._subtitle_panel.isHidden()
        assert "Hi." in view._subtitle_panel.preview_text

    def test_worker_finished_re_enables_button(self, view):
        view.download_btn.setEnabled(False)
        view._on_worker_finished()
        assert view.download_btn.isEnabled()

    def test_worker_finished_sets_complete_on_panel(self, view):
        view._active_panel.show()
        view._on_worker_finished()
        assert view._active_panel.bar_value == 100
