"""Tests for src.scene_detector — FFmpeg scene change detection."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config_loader import Config
from src.models import FrameInfo
from src.scene_detector import SceneDetector, _SHOWINFO_RE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cfg(**overrides) -> Config:
    data = {
        "scene": {
            "threshold": 0.3,
            "output_dir": "output/frames",
            "format": "jpg",
            **overrides,
        }
    }
    return Config(data)


def _fake_run(returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stderr = stderr
    return result


_SHOWINFO_SAMPLE = """
ffmpeg version 6.1 Copyright (c) 2000-2023 the FFmpeg developers
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'lecture.mp4':
[Parsed_showinfo_1 @ 0x60000380e000] n:   0 pts:      0 pts_time:0       pos:       888 fmt:yuv420p sar:1/1 s:1920x1080 i:P iskey:1 type:I checksum:XXXXXXXX plane_checksum:[XXXXXXXX XXXXXXXX XXXXXXXX]
[Parsed_showinfo_1 @ 0x60000380e000] n:   1 pts:  90090 pts_time:10.01   pos:  5240512 fmt:yuv420p sar:1/1 s:1920x1080 i:P iskey:0 type:P checksum:XXXXXXXX plane_checksum:[XXXXXXXX XXXXXXXX XXXXXXXX]
[Parsed_showinfo_1 @ 0x60000380e000] n:   2 pts: 180180 pts_time:20.02   pos: 10480512 fmt:yuv420p sar:1/1 s:1920x1080 i:P iskey:0 type:P checksum:XXXXXXXX plane_checksum:[XXXXXXXX XXXXXXXX XXXXXXXX]
"""


# ---------------------------------------------------------------------------
# _SHOWINFO_RE pattern
# ---------------------------------------------------------------------------

def test_showinfo_regex_parses_n_and_pts_time():
    matches = list(_SHOWINFO_RE.finditer(_SHOWINFO_SAMPLE))
    assert len(matches) == 3
    assert matches[0].group(1) == "0"
    assert matches[0].group(2) == "0"
    assert matches[1].group(1) == "1"
    assert float(matches[1].group(2)) == pytest.approx(10.01)
    assert matches[2].group(1) == "2"
    assert float(matches[2].group(2)) == pytest.approx(20.02)


# ---------------------------------------------------------------------------
# SceneDetector construction
# ---------------------------------------------------------------------------

def test_reads_threshold_from_config():
    det = SceneDetector(_cfg(threshold=0.5))
    assert det.threshold == 0.5


def test_reads_format_from_config():
    det = SceneDetector(_cfg(format="png"))
    assert det.fmt == "png"


# ---------------------------------------------------------------------------
# detect() — success path
# ---------------------------------------------------------------------------

@patch("src.scene_detector.subprocess.run")
def test_detect_returns_frame_info_list(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr=_SHOWINFO_SAMPLE)
    det = SceneDetector(_cfg())
    frames = det.detect("lecture.mp4", output_dir=tmp_path)

    assert len(frames) == 3
    assert all(isinstance(f, FrameInfo) for f in frames)


@patch("src.scene_detector.subprocess.run")
def test_detect_frame_timestamps(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr=_SHOWINFO_SAMPLE)
    det = SceneDetector(_cfg())
    frames = det.detect("lecture.mp4", output_dir=tmp_path)

    assert frames[0].timestamp == pytest.approx(0.0)
    assert frames[1].timestamp == pytest.approx(10.01)
    assert frames[2].timestamp == pytest.approx(20.02)


@patch("src.scene_detector.subprocess.run")
def test_detect_frame_indices_are_1_based(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr=_SHOWINFO_SAMPLE)
    det = SceneDetector(_cfg())
    frames = det.detect("lecture.mp4", output_dir=tmp_path)

    assert frames[0].frame_index == 1
    assert frames[1].frame_index == 2
    assert frames[2].frame_index == 3


@patch("src.scene_detector.subprocess.run")
def test_detect_frame_paths_use_output_dir(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr=_SHOWINFO_SAMPLE)
    det = SceneDetector(_cfg())
    frames = det.detect("lecture.mp4", output_dir=tmp_path)

    for f in frames:
        assert str(tmp_path) in f.frame_path


@patch("src.scene_detector.subprocess.run")
def test_detect_uses_threshold_in_ffmpeg_cmd(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr="")
    det = SceneDetector(_cfg(threshold=0.4))
    det.detect("v.mp4", output_dir=tmp_path)

    call_args = mock_run.call_args[0][0]  # positional argv list
    vf_arg = call_args[call_args.index("-vf") + 1]
    assert "0.4" in vf_arg


@patch("src.scene_detector.subprocess.run")
def test_detect_sorted_by_timestamp(mock_run, tmp_path):
    # Deliberately unsorted showinfo output
    unsorted_stderr = (
        "[Parsed_showinfo_1 @ 0x0] n:   1 pts: 90090 pts_time:10.01 ...\n"
        "[Parsed_showinfo_1 @ 0x0] n:   0 pts:     0 pts_time:0 ...\n"
    )
    mock_run.return_value = _fake_run(stderr=unsorted_stderr)
    det = SceneDetector(_cfg())
    frames = det.detect("v.mp4", output_dir=tmp_path)

    timestamps = [f.timestamp for f in frames]
    assert timestamps == sorted(timestamps)


# ---------------------------------------------------------------------------
# detect() — error paths
# ---------------------------------------------------------------------------

@patch("src.scene_detector.subprocess.run")
def test_detect_empty_stderr_returns_empty(mock_run, tmp_path):
    mock_run.return_value = _fake_run(stderr="some ffmpeg output with no showinfo")
    det = SceneDetector(_cfg())
    frames = det.detect("v.mp4", output_dir=tmp_path)
    assert frames == []


@patch("src.scene_detector.subprocess.run", side_effect=FileNotFoundError)
def test_detect_ffmpeg_not_found_returns_empty(mock_run, tmp_path):
    det = SceneDetector(_cfg())
    frames = det.detect("v.mp4", output_dir=tmp_path)
    assert frames == []


@patch("src.scene_detector.subprocess.run")
def test_detect_nonzero_exit_still_returns_frames(mock_run, tmp_path):
    # FFmpeg may exit non-zero but still produce valid showinfo output
    mock_run.return_value = _fake_run(returncode=1, stderr=_SHOWINFO_SAMPLE)
    det = SceneDetector(_cfg())
    frames = det.detect("v.mp4", output_dir=tmp_path)
    assert len(frames) == 3


# ---------------------------------------------------------------------------
# Integration — skip if ffmpeg not available
# ---------------------------------------------------------------------------

ffmpeg_available = pytest.mark.skipif(
    subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0,
    reason="FFmpeg not installed",
)
