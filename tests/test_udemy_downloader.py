"""Tests for src/udemy_downloader.py — TDD suite (all yt-dlp calls mocked)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from src.models import DownloadResult
from src.udemy_downloader import (
    UdemyDownloader,
    UdemyDownloaderConfig,
    UdemyDownloadResult,
    load_udemy_downloader_from_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_URL = "https://www.udemy.com/course/deep-learning-ai/learn/lecture/123456"
DEFAULT_CONFIG = UdemyDownloaderConfig(output_dir="output/udemy")


def make_entry_info(
    video_id: str = "udm001",
    title: str = "Lecture 1",
    ext: str = "mp4",
    webpage_url: str = TEST_URL,
    requested_subtitles: dict | None = None,
    subtitles: dict | None = None,
) -> dict:
    return {
        "id": video_id,
        "title": title,
        "ext": ext,
        "webpage_url": webpage_url,
        "subtitles": subtitles or {},
        "requested_subtitles": requested_subtitles,
    }


def make_entry_with_srt(tmp_path: Path, creator: bool = True) -> dict:
    srt = tmp_path / "lecture.srt"
    srt.touch()
    creator_subs = {"en": [{"url": "..."}]} if creator else {}
    return make_entry_info(
        requested_subtitles={"en": {"filepath": str(srt)}},
        subtitles=creator_subs,
    )


def _download_with_mock(info: dict, config: UdemyDownloaderConfig = DEFAULT_CONFIG) -> UdemyDownloadResult:
    with patch("src.udemy_downloader.yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl = MockYDL.return_value.__enter__.return_value
        mock_ydl.extract_info.return_value = info
        return UdemyDownloader(config).download(TEST_URL)


def _download_raising(exc: Exception, config: UdemyDownloaderConfig = DEFAULT_CONFIG) -> UdemyDownloadResult:
    with patch("src.udemy_downloader.yt_dlp.YoutubeDL") as MockYDL:
        mock_ydl = MockYDL.return_value.__enter__.return_value
        mock_ydl.extract_info.side_effect = exc
        return UdemyDownloader(config).download(TEST_URL)


# ---------------------------------------------------------------------------
# TestUdemyDownloadResult
# ---------------------------------------------------------------------------

class TestUdemyDownloadResult:
    def test_drm_blocked_true_has_no_download_result(self):
        r = UdemyDownloadResult(drm_blocked=True, download_result=None)
        assert r.drm_blocked is True
        assert r.download_result is None

    def test_success_has_download_result(self):
        dr = DownloadResult(
            video_id="x", title="t", video_path="/p.mp4",
            subtitle_path=None, subtitle_fallback=False,
            srt_not_found=True, webpage_url=TEST_URL,
        )
        r = UdemyDownloadResult(drm_blocked=False, download_result=dr)
        assert r.drm_blocked is False
        assert r.download_result is dr


# ---------------------------------------------------------------------------
# TestUdemyDownloaderConfig
# ---------------------------------------------------------------------------

class TestUdemyDownloaderConfig:
    def test_default_browser_is_chrome(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp/dl")
        assert cfg.browser == "chrome"

    def test_default_subtitle_langs(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp/dl")
        assert cfg.subtitle_langs == ["en"]

    def test_default_subtitle_format(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp/dl")
        assert cfg.subtitle_format == "srt"

    def test_default_quiet_flags(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp/dl")
        assert cfg.quiet is True
        assert cfg.no_warnings is True

    def test_custom_browser(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp/dl", browser="firefox")
        assert cfg.browser == "firefox"

    def test_custom_values(self):
        cfg = UdemyDownloaderConfig(
            output_dir="/out",
            browser="safari",
            subtitle_langs=["en", "vi"],
            quiet=False,
        )
        assert cfg.output_dir == "/out"
        assert cfg.browser == "safari"
        assert cfg.subtitle_langs == ["en", "vi"]
        assert cfg.quiet is False


# ---------------------------------------------------------------------------
# TestDownloadSuccess
# ---------------------------------------------------------------------------

class TestDownloadSuccess:
    def test_returns_udemy_download_result(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        result = _download_with_mock(info)
        assert isinstance(result, UdemyDownloadResult)

    def test_drm_blocked_false_on_success(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        result = _download_with_mock(info)
        assert result.drm_blocked is False

    def test_download_result_not_none_on_success(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        result = _download_with_mock(info)
        assert result.download_result is not None

    def test_download_result_is_download_result_type(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        result = _download_with_mock(info)
        assert isinstance(result.download_result, DownloadResult)

    def test_video_id_populated(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        info["id"] = "udm999"
        result = _download_with_mock(info)
        assert result.download_result.video_id == "udm999"

    def test_title_populated(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        info["title"] = "Intro to CNNs"
        result = _download_with_mock(info)
        assert result.download_result.title == "Intro to CNNs"

    def test_webpage_url_populated(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        result = _download_with_mock(info)
        assert result.download_result.webpage_url == TEST_URL

    def test_extract_info_called_with_url(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        with patch("src.udemy_downloader.yt_dlp.YoutubeDL") as MockYDL:
            mock_ydl = MockYDL.return_value.__enter__.return_value
            mock_ydl.extract_info.return_value = info
            UdemyDownloader(DEFAULT_CONFIG).download(TEST_URL)
        mock_ydl.extract_info.assert_called_once_with(TEST_URL, download=True)

    def test_output_dir_created(self, tmp_path):
        info = make_entry_with_srt(tmp_path)
        out_dir = tmp_path / "new_udemy_dir"
        cfg = UdemyDownloaderConfig(output_dir=str(out_dir))
        _download_with_mock(info, cfg)
        assert out_dir.exists()


# ---------------------------------------------------------------------------
# TestDrmBlocked
# ---------------------------------------------------------------------------

class TestDrmBlocked:
    def _403_error(self, msg: str = "HTTP Error 403: Forbidden") -> yt_dlp.utils.DownloadError:
        return yt_dlp.utils.DownloadError(msg)

    def test_http_403_sets_drm_blocked_true(self):
        result = _download_raising(self._403_error("HTTP Error 403: Forbidden"))
        assert result.drm_blocked is True

    def test_bare_403_in_message_sets_drm_blocked_true(self):
        result = _download_raising(self._403_error("ERROR: 403 when downloading fragment"))
        assert result.drm_blocked is True

    def test_drm_in_message_sets_drm_blocked_true(self):
        result = _download_raising(self._403_error("DRM-protected content"))
        assert result.drm_blocked is True

    def test_forbidden_in_message_sets_drm_blocked_true(self):
        result = _download_raising(self._403_error("Forbidden: access denied"))
        assert result.drm_blocked is True

    def test_drm_blocked_result_has_no_download_result(self):
        result = _download_raising(self._403_error())
        assert result.download_result is None

    def test_drm_blocked_does_not_raise(self):
        # Should return gracefully, not propagate the exception
        try:
            _download_raising(self._403_error())
        except Exception as exc:
            pytest.fail(f"download() raised unexpectedly: {exc}")

    def test_case_insensitive_drm_detection(self):
        result = _download_raising(self._403_error("drm encrypted video"))
        assert result.drm_blocked is True

    def test_case_insensitive_forbidden_detection(self):
        result = _download_raising(self._403_error("FORBIDDEN content"))
        assert result.drm_blocked is True


# ---------------------------------------------------------------------------
# TestNonDrmErrorReraises
# ---------------------------------------------------------------------------

class TestNonDrmErrorReraises:
    def test_network_error_reraises(self):
        exc = yt_dlp.utils.DownloadError("Network unreachable")
        with pytest.raises(yt_dlp.utils.DownloadError):
            _download_raising(exc)

    def test_invalid_url_error_reraises(self):
        exc = yt_dlp.utils.DownloadError("Unable to extract URL")
        with pytest.raises(yt_dlp.utils.DownloadError):
            _download_raising(exc)

    def test_unexpected_exception_reraises(self):
        exc = RuntimeError("something unexpected")
        with pytest.raises(RuntimeError):
            _download_raising(exc)


# ---------------------------------------------------------------------------
# TestBuildYdlParams
# ---------------------------------------------------------------------------

class TestBuildYdlParams:
    def test_cookiesfrombrowser_uses_configured_browser(self):
        cfg = UdemyDownloaderConfig(output_dir="/tmp", browser="firefox")
        params = UdemyDownloader(cfg)._build_ydl_params(TEST_URL)
        # cookiesfrombrowser value must reference "firefox"
        cbfb = params["cookiesfrombrowser"]
        assert "firefox" in (cbfb if isinstance(cbfb, str) else cbfb[0])

    def test_referer_matches_url(self):
        params = UdemyDownloader(DEFAULT_CONFIG)._build_ydl_params(TEST_URL)
        referer = params.get("referer") or params.get("http_headers", {}).get("Referer", "")
        assert TEST_URL in referer

    def test_outtmpl_contains_output_dir(self):
        cfg = UdemyDownloaderConfig(output_dir="/my/udemy")
        params = UdemyDownloader(cfg)._build_ydl_params(TEST_URL)
        assert "/my/udemy" in params["outtmpl"]

    def test_format_in_params(self):
        params = UdemyDownloader(DEFAULT_CONFIG)._build_ydl_params(TEST_URL)
        assert params["format"] == DEFAULT_CONFIG.format

    def test_subtitle_params(self):
        params = UdemyDownloader(DEFAULT_CONFIG)._build_ydl_params(TEST_URL)
        assert params["writesubtitles"] is True
        assert params["subtitleslangs"] == ["en"]
        assert params["subtitlesformat"] == "srt"

    def test_quiet_and_no_warnings(self):
        params = UdemyDownloader(DEFAULT_CONFIG)._build_ydl_params(TEST_URL)
        assert params["quiet"] is True
        assert params["no_warnings"] is True


# ---------------------------------------------------------------------------
# TestSubtitleStatus  (mirrors YouTubeDownloader subtitle tests)
# ---------------------------------------------------------------------------

class TestSubtitleStatus:
    def test_creator_subtitle_detected(self, tmp_path):
        info = make_entry_with_srt(tmp_path, creator=True)
        result = _download_with_mock(info)
        dr = result.download_result
        assert dr.subtitle_fallback is False
        assert dr.srt_not_found is False

    def test_auto_caption_sets_fallback_true(self, tmp_path):
        info = make_entry_with_srt(tmp_path, creator=False)  # auto-gen only
        result = _download_with_mock(info)
        assert result.download_result.subtitle_fallback is True

    def test_no_subtitles_sets_srt_not_found(self):
        info = make_entry_info(requested_subtitles=None, subtitles={})
        result = _download_with_mock(info)
        dr = result.download_result
        assert dr.srt_not_found is True
        assert dr.subtitle_path is None

    def test_filepath_missing_from_disk_sets_srt_not_found(self, tmp_path):
        missing = str(tmp_path / "ghost.srt")
        info = make_entry_info(
            requested_subtitles={"en": {"filepath": missing}},
            subtitles={"en": [{"url": "..."}]},
        )
        result = _download_with_mock(info)
        assert result.download_result.srt_not_found is True


# ---------------------------------------------------------------------------
# TestLoadFromConfig
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_output_dir_from_yaml(self):
        dl = load_udemy_downloader_from_config("config/config.yaml")
        assert dl.config.output_dir == "output/udemy"

    def test_browser_from_yaml(self):
        dl = load_udemy_downloader_from_config("config/config.yaml")
        assert dl.config.browser == "chrome"

    def test_output_dir_override(self):
        dl = load_udemy_downloader_from_config(
            "config/config.yaml", output_dir="/override"
        )
        assert dl.config.output_dir == "/override"

    def test_missing_udemy_section_uses_defaults(self, tmp_path):
        cfg_path = tmp_path / "min.yaml"
        cfg_path.write_text("app:\n  log_level: INFO\n", encoding="utf-8")
        dl = load_udemy_downloader_from_config(str(cfg_path))
        assert dl.config.browser == "chrome"
        assert dl.config.output_dir == "output/udemy"
