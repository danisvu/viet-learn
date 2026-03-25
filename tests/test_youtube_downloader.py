"""Tests for src/youtube_downloader.py — TDD suite (38 tests)."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.models import DownloadResult
from src.youtube_downloader import (
    YouTubeDownloader,
    YouTubeDownloaderConfig,
    load_youtube_downloader_from_config,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_entry_info(
    video_id: str = "abc123",
    title: str = "Test Video",
    ext: str = "mp4",
    webpage_url: str = "https://www.youtube.com/watch?v=abc123",
    requested_subtitles: dict | None = None,
    subtitles: dict | None = None,
    sub_filepath: str | None = None,
    sub_lang: str = "en",
) -> dict:
    """Build a minimal yt-dlp entry info dict."""
    info: dict = {
        "id": video_id,
        "title": title,
        "ext": ext,
        "webpage_url": webpage_url,
        "subtitles": subtitles or {},
        "requested_subtitles": requested_subtitles,
    }
    if requested_subtitles is not None and sub_filepath is not None:
        info["requested_subtitles"] = {sub_lang: {"filepath": sub_filepath}}
    return info


DEFAULT_CONFIG = YouTubeDownloaderConfig(output_dir="output/downloads")
TEST_URL = "https://www.youtube.com/watch?v=abc123"


# ---------------------------------------------------------------------------
# TestDownloadResult
# ---------------------------------------------------------------------------

class TestDownloadResult:
    def test_fields_exist(self):
        r = DownloadResult(
            video_id="abc",
            title="My Video",
            video_path="/tmp/video.mp4",
            subtitle_path="/tmp/video.srt",
            subtitle_fallback=False,
            srt_not_found=False,
            webpage_url="https://youtube.com/watch?v=abc",
        )
        assert r.video_id == "abc"
        assert r.title == "My Video"
        assert r.video_path == "/tmp/video.mp4"
        assert r.subtitle_path == "/tmp/video.srt"
        assert r.subtitle_fallback is False
        assert r.srt_not_found is False
        assert r.webpage_url == "https://youtube.com/watch?v=abc"


# ---------------------------------------------------------------------------
# TestYouTubeDownloaderConfig
# ---------------------------------------------------------------------------

class TestYouTubeDownloaderConfig:
    def test_defaults(self):
        cfg = YouTubeDownloaderConfig(output_dir="/tmp/dl")
        assert cfg.format == "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4"
        assert cfg.subtitle_langs == ["en"]
        assert cfg.subtitle_format == "srt"
        assert cfg.quiet is True
        assert cfg.no_warnings is True

    def test_custom_values(self):
        cfg = YouTubeDownloaderConfig(
            output_dir="/my/dir",
            format="best",
            subtitle_langs=["vi", "en"],
            subtitle_format="vtt",
            quiet=False,
            no_warnings=False,
        )
        assert cfg.output_dir == "/my/dir"
        assert cfg.format == "best"
        assert cfg.subtitle_langs == ["vi", "en"]
        assert cfg.subtitle_format == "vtt"
        assert cfg.quiet is False
        assert cfg.no_warnings is False


# ---------------------------------------------------------------------------
# TestDownloadSingleVideo
# ---------------------------------------------------------------------------

class TestDownloadSingleVideo:
    def _make_info(self, tmp_path: Path) -> dict:
        srt = str(tmp_path / "video.srt")
        Path(srt).touch()
        return make_entry_info(
            video_id="abc123",
            title="Test Video",
            requested_subtitles={"en": {"filepath": srt}},
            subtitles={"en": [{"url": "..."}]},
            sub_filepath=srt,
        )

    def test_returns_list_of_one(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            downloader = YouTubeDownloader(DEFAULT_CONFIG)
            results = downloader.download(TEST_URL)
        assert isinstance(results, list)
        assert len(results) == 1

    def test_result_video_id(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].video_id == "abc123"

    def test_result_title(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].title == "Test Video"

    def test_result_video_path(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            mock_ydl.prepare_filename.return_value = str(tmp_path / "Test Video [abc123].mp4")
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].video_path.endswith(".mp4")

    def test_result_webpage_url(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].webpage_url == TEST_URL

    def test_creator_sub_detected(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].subtitle_fallback is False
        assert results[0].srt_not_found is False

    def test_extract_info_called_with_url(self, tmp_path):
        info = self._make_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        mock_ydl.extract_info.assert_called_once_with(TEST_URL, download=True)

    def test_ydl_params_correctness(self):
        downloader = YouTubeDownloader(DEFAULT_CONFIG)
        params = downloader._build_ydl_params()
        assert params["writesubtitles"] is True
        assert params["writeautomaticsub"] is True
        assert params["subtitleslangs"] == ["en"]
        assert params["subtitlesformat"] == "srt"
        assert params["noplaylist"] is False
        assert params["ignoreerrors"] is True


# ---------------------------------------------------------------------------
# TestDownloadNoSubtitles
# ---------------------------------------------------------------------------

class TestDownloadNoSubtitles:
    def _make_no_sub_info(self) -> dict:
        return make_entry_info(
            video_id="xyz999",
            title="No Sub Video",
            requested_subtitles=None,
            subtitles={},
        )

    def test_srt_not_found_true(self):
        info = self._make_no_sub_info()
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].srt_not_found is True

    def test_subtitle_path_none(self):
        info = self._make_no_sub_info()
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].subtitle_path is None

    def test_fallback_false_when_no_sub(self):
        info = self._make_no_sub_info()
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].subtitle_fallback is False

    def test_filepath_missing_from_disk(self, tmp_path):
        # filepath in dict but file doesn't exist on disk
        missing_path = str(tmp_path / "nonexistent.srt")
        info = make_entry_info(
            video_id="xyz999",
            title="Missing SRT",
            requested_subtitles={"en": {"filepath": missing_path}},
            subtitles={"en": [{"url": "..."}]},
            sub_filepath=missing_path,
        )
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].srt_not_found is True
        assert results[0].subtitle_path is None


# ---------------------------------------------------------------------------
# TestAutoSubFallback
# ---------------------------------------------------------------------------

class TestAutoSubFallback:
    def test_subtitle_fallback_true_when_only_auto_captions(self, tmp_path):
        srt = str(tmp_path / "auto.srt")
        Path(srt).touch()
        # requested_subtitles has "en", but subtitles (creator) does NOT
        info = make_entry_info(
            video_id="auto001",
            title="Auto Cap Video",
            requested_subtitles={"en": {"filepath": srt}},
            subtitles={},   # no creator subtitles → auto-generated
            sub_filepath=srt,
        )
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert results[0].subtitle_fallback is True
        assert results[0].srt_not_found is False
        assert results[0].subtitle_path == srt


# ---------------------------------------------------------------------------
# TestDownloadPlaylist
# ---------------------------------------------------------------------------

class TestDownloadPlaylist:
    def _make_playlist_info(self, tmp_path: Path) -> dict:
        srt1 = str(tmp_path / "v1.srt")
        srt2 = str(tmp_path / "v2.srt")
        Path(srt1).touch()
        Path(srt2).touch()
        return {
            "_type": "playlist",
            "id": "PLabc",
            "title": "My Playlist",
            "entries": [
                make_entry_info("v1", "Video 1", sub_filepath=srt1,
                                requested_subtitles={"en": {"filepath": srt1}},
                                subtitles={"en": [{"url": "..."}]}),
                None,  # ignoreerrors may produce None entries
                make_entry_info("v2", "Video 2", sub_filepath=srt2,
                                requested_subtitles={"en": {"filepath": srt2}},
                                subtitles={"en": [{"url": "..."}]}),
            ],
        }

    def test_multiple_results(self, tmp_path):
        info = self._make_playlist_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        assert len(results) == 2

    def test_skip_none_entries(self, tmp_path):
        info = self._make_playlist_info(tmp_path)
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            results = YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL)
        # None entry filtered → only 2 valid results
        assert all(r is not None for r in results)
        assert len(results) == 2

    def test_progress_callback_per_video(self, tmp_path):
        info = self._make_playlist_info(tmp_path)
        calls = []

        def cb(current: int, total: int, title: str) -> None:
            calls.append((current, total, title))

        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL, progress_callback=cb)
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# TestProgressCallback
# ---------------------------------------------------------------------------

class TestProgressCallback:
    def test_callback_receives_current_total_title(self, tmp_path):
        srt = str(tmp_path / "a.srt")
        Path(srt).touch()
        info = {
            "_type": "playlist",
            "id": "PL1",
            "entries": [
                make_entry_info("v1", "First", sub_filepath=srt,
                                requested_subtitles={"en": {"filepath": srt}},
                                subtitles={"en": [{"url": "..."}]}),
            ],
        }
        received = []

        def cb(current, total, title):
            received.append((current, total, title))

        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL, progress_callback=cb)
        assert received[0][0] == 1       # current
        assert received[0][1] == 1       # total
        assert received[0][2] == "First" # title

    def test_callback_not_required(self, tmp_path):
        srt = str(tmp_path / "a.srt")
        Path(srt).touch()
        info = make_entry_info("v1", "Solo", sub_filepath=srt,
                               requested_subtitles={"en": {"filepath": srt}},
                               subtitles={"en": [{"url": "..."}]})
        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            # Should not raise
            YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL, progress_callback=None)

    def test_callback_in_order(self, tmp_path):
        srts = []
        entries = []
        for i in range(3):
            srt = str(tmp_path / f"s{i}.srt")
            Path(srt).touch()
            srts.append(srt)
            entries.append(make_entry_info(f"v{i}", f"Video {i}", sub_filepath=srt,
                                           requested_subtitles={"en": {"filepath": srt}},
                                           subtitles={"en": [{"url": "..."}]}))
        info = {"_type": "playlist", "id": "PL2", "entries": entries}
        order = []

        def cb(current, total, title):
            order.append(current)

        with patch("src.youtube_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            YouTubeDownloader(DEFAULT_CONFIG).download(TEST_URL, progress_callback=cb)
        assert order == [1, 2, 3]


# ---------------------------------------------------------------------------
# TestBuildYdlParams
# ---------------------------------------------------------------------------

class TestBuildYdlParams:
    def test_outtmpl_contains_output_dir(self):
        cfg = YouTubeDownloaderConfig(output_dir="/my/downloads")
        params = YouTubeDownloader(cfg)._build_ydl_params()
        assert "/my/downloads" in params["outtmpl"]

    def test_format_in_params(self):
        params = YouTubeDownloader(DEFAULT_CONFIG)._build_ydl_params()
        assert params["format"] == DEFAULT_CONFIG.format

    def test_subtitle_params(self):
        params = YouTubeDownloader(DEFAULT_CONFIG)._build_ydl_params()
        assert params["writesubtitles"] is True
        assert params["writeautomaticsub"] is True
        assert params["subtitleslangs"] == ["en"]
        assert params["subtitlesformat"] == "srt"

    def test_quiet_and_no_warnings(self):
        params = YouTubeDownloader(DEFAULT_CONFIG)._build_ydl_params()
        assert params["quiet"] is True
        assert params["no_warnings"] is True


# ---------------------------------------------------------------------------
# TestExtractEntries
# ---------------------------------------------------------------------------

class TestExtractEntries:
    def test_single_video_returns_list_of_one(self):
        info = make_entry_info("v1", "Solo")
        downloader = YouTubeDownloader(DEFAULT_CONFIG)
        entries = downloader._extract_entries(info)
        assert entries == [info]

    def test_playlist_returns_entries(self, tmp_path):
        e1 = make_entry_info("v1", "A")
        e2 = make_entry_info("v2", "B")
        info = {"_type": "playlist", "entries": [e1, e2]}
        entries = YouTubeDownloader(DEFAULT_CONFIG)._extract_entries(info)
        assert entries == [e1, e2]

    def test_none_entries_filtered(self):
        e1 = make_entry_info("v1", "A")
        info = {"_type": "playlist", "entries": [e1, None]}
        entries = YouTubeDownloader(DEFAULT_CONFIG)._extract_entries(info)
        assert None not in entries
        assert len(entries) == 1

    def test_multi_video_type_handled(self):
        e1 = make_entry_info("v1", "A")
        info = {"_type": "multi_video", "entries": [e1]}
        entries = YouTubeDownloader(DEFAULT_CONFIG)._extract_entries(info)
        assert entries == [e1]


# ---------------------------------------------------------------------------
# TestLoadFromConfig
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_output_dir_from_yaml(self):
        downloader = load_youtube_downloader_from_config("config/config.yaml")
        assert downloader.config.output_dir == "output/downloads"

    def test_output_dir_override(self):
        downloader = load_youtube_downloader_from_config(
            "config/config.yaml", output_dir="/custom/dir"
        )
        assert downloader.config.output_dir == "/custom/dir"

    def test_missing_download_section_uses_defaults(self, tmp_path):
        yaml_content = "app:\n  log_level: INFO\n"
        cfg_path = str(tmp_path / "min.yaml")
        Path(cfg_path).write_text(yaml_content)
        downloader = load_youtube_downloader_from_config(cfg_path)
        # Should fall back to dataclass defaults
        assert downloader.config.subtitle_langs == ["en"]
        assert downloader.config.subtitle_format == "srt"


# ---------------------------------------------------------------------------
# TestIntegration — network tests (skipped by default)
# ---------------------------------------------------------------------------

def _has_network() -> bool:
    try:
        import socket
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_network(), reason="No network access")
class TestIntegration:
    def test_real_download_short_video(self, tmp_path):
        """Download a very short public domain YouTube video to verify end-to-end."""
        cfg = YouTubeDownloaderConfig(
            output_dir=str(tmp_path),
            format="worstvideo+worstaudio/worst",
        )
        downloader = YouTubeDownloader(cfg)
        # 5-second NASA public domain video
        url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
        results = downloader.download(url)
        assert len(results) >= 1
        assert Path(results[0].video_path).exists()
