"""Tests for src/audio_capture.py — TDD suite (all PyAudio calls mocked)."""
from __future__ import annotations

import threading
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.audio_capture import (
    AudioCapture,
    CaptureConfig,
    DeviceNotFoundError,
    load_audio_capture_from_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_DEVICES = [
    {"name": "Built-in Microphone", "index": 0},
    {"name": "BlackHole 2ch",       "index": 1},
    {"name": "Built-in Output",     "index": 2},
]


def _device_lookup(devices: list[dict]):
    """Return a side_effect callable that looks up a device by iteration index."""
    def _get(i):
        return devices[i]
    return _get


@pytest.fixture
def mock_pa(tmp_path):
    """Patch src.audio_capture.pyaudio for the duration of a test."""
    with patch("src.audio_capture.pyaudio") as mock_module:
        mock_module.paInt16 = 8  # matches real PyAudio constant

        pa_inst = MagicMock()
        mock_module.PyAudio.return_value = pa_inst

        pa_inst.get_device_count.return_value = len(DEFAULT_DEVICES)
        pa_inst.get_device_info_by_index.side_effect = _device_lookup(DEFAULT_DEVICES)

        mock_stream = MagicMock()
        mock_stream.read.return_value = b"\x00" * 2048
        pa_inst.open.return_value = mock_stream

        yield mock_module, pa_inst, mock_stream


def make_capture(tmp_path: Path, **cfg_kwargs) -> AudioCapture:
    cfg_kwargs.setdefault("output_dir", str(tmp_path))
    return AudioCapture(CaptureConfig(**cfg_kwargs))


def start_and_stop(
    capture: AudioCapture, output_path: str
) -> str:
    """Start recording then immediately stop. Returns output_path."""
    capture.start(output_path)
    return capture.stop()


def open_wav_for_writing(path: str, channels: int = 2, rate: int = 44100) -> wave.Wave_write:
    wf = wave.open(path, "wb")
    wf.setnchannels(channels)
    wf.setsampwidth(2)
    wf.setframerate(rate)
    return wf


# ---------------------------------------------------------------------------
# TestCaptureConfig
# ---------------------------------------------------------------------------

class TestCaptureConfig:
    def test_default_device_name(self):
        assert CaptureConfig().device_name == "BlackHole 2ch"

    def test_default_sample_rate(self):
        assert CaptureConfig().sample_rate == 44100

    def test_default_channels(self):
        assert CaptureConfig().channels == 2

    def test_default_chunk_size(self):
        assert CaptureConfig().chunk_size == 1024

    def test_default_output_dir(self):
        assert CaptureConfig().output_dir == "output/captures"

    def test_custom_values(self):
        cfg = CaptureConfig(
            output_dir="/custom",
            device_name="My Device",
            sample_rate=48000,
            channels=1,
            chunk_size=512,
        )
        assert cfg.output_dir == "/custom"
        assert cfg.device_name == "My Device"
        assert cfg.sample_rate == 48000
        assert cfg.channels == 1
        assert cfg.chunk_size == 512


# ---------------------------------------------------------------------------
# TestIsRecording
# ---------------------------------------------------------------------------

class TestIsRecording:
    def test_false_before_start(self, tmp_path):
        capture = make_capture(tmp_path)
        assert capture.is_recording() is False

    def test_true_after_start(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        capture.start(str(tmp_path / "out.wav"))
        assert capture.is_recording() is True
        capture.stop()

    def test_false_after_stop(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        assert capture.is_recording() is False


# ---------------------------------------------------------------------------
# TestStartRecording
# ---------------------------------------------------------------------------

class TestStartRecording:
    def test_pyaudio_constructor_called(self, tmp_path, mock_pa):
        mock_module, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path)
        capture.start(str(tmp_path / "out.wav"))
        capture.stop()
        mock_module.PyAudio.assert_called()

    def test_stream_opened_with_input_true(self, tmp_path, mock_pa):
        _, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        kwargs = pa_inst.open.call_args.kwargs
        assert kwargs.get("input") is True

    def test_stream_format_is_paInt16(self, tmp_path, mock_pa):
        mock_module, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        kwargs = pa_inst.open.call_args.kwargs
        assert kwargs.get("format") == mock_module.paInt16

    def test_stream_uses_configured_sample_rate(self, tmp_path, mock_pa):
        _, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path, sample_rate=48000)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        assert pa_inst.open.call_args.kwargs.get("rate") == 48000

    def test_stream_uses_configured_channels(self, tmp_path, mock_pa):
        _, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path, channels=1)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        assert pa_inst.open.call_args.kwargs.get("channels") == 1

    def test_stream_passes_blackhole_device_index(self, tmp_path, mock_pa):
        _, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        # BlackHole 2ch has index=1 in DEFAULT_DEVICES
        assert pa_inst.open.call_args.kwargs.get("input_device_index") == 1

    def test_output_dir_created_if_missing(self, tmp_path, mock_pa):
        out_dir = tmp_path / "deep" / "nested"
        capture = AudioCapture(CaptureConfig(output_dir=str(out_dir)))
        capture.start(str(out_dir / "out.wav"))
        capture.stop()
        assert out_dir.exists()

    def test_recording_thread_is_daemon(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        capture.start(str(tmp_path / "out.wav"))
        assert capture._thread.daemon is True
        capture.stop()


# ---------------------------------------------------------------------------
# TestStopRecording
# ---------------------------------------------------------------------------

class TestStopRecording:
    def test_returns_output_path(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        output_path = str(tmp_path / "capture.wav")
        capture.start(output_path)
        result = capture.stop()
        assert result == output_path

    def test_wav_file_created_on_disk(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        output_path = str(tmp_path / "capture.wav")
        start_and_stop(capture, output_path)
        assert Path(output_path).exists()

    def test_wav_sample_rate_correct(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path, sample_rate=44100)
        output_path = str(tmp_path / "capture.wav")
        start_and_stop(capture, output_path)
        with wave.open(output_path, "rb") as wf:
            assert wf.getframerate() == 44100

    def test_wav_channels_correct(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path, channels=2)
        output_path = str(tmp_path / "capture.wav")
        start_and_stop(capture, output_path)
        with wave.open(output_path, "rb") as wf:
            assert wf.getnchannels() == 2

    def test_wav_sample_width_is_16bit(self, tmp_path, mock_pa):
        """16-bit PCM = 2 bytes sample width."""
        capture = make_capture(tmp_path)
        output_path = str(tmp_path / "capture.wav")
        start_and_stop(capture, output_path)
        with wave.open(output_path, "rb") as wf:
            assert wf.getsampwidth() == 2

    def test_stream_stopped_and_closed(self, tmp_path, mock_pa):
        _, pa_inst, mock_stream = mock_pa
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_pyaudio_terminated(self, tmp_path, mock_pa):
        _, pa_inst, _ = mock_pa
        capture = make_capture(tmp_path)
        start_and_stop(capture, str(tmp_path / "out.wav"))
        pa_inst.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# TestStateErrors
# ---------------------------------------------------------------------------

class TestStateErrors:
    def test_start_twice_raises(self, tmp_path, mock_pa):
        capture = make_capture(tmp_path)
        capture.start(str(tmp_path / "a.wav"))
        with pytest.raises(RuntimeError, match="[Aa]lready"):
            capture.start(str(tmp_path / "b.wav"))
        capture.stop()

    def test_stop_before_start_raises(self, tmp_path):
        capture = make_capture(tmp_path)
        with pytest.raises(RuntimeError, match="[Nn]o recording"):
            capture.stop()


# ---------------------------------------------------------------------------
# TestPyAudioNotInstalled
# ---------------------------------------------------------------------------

class TestPyAudioNotInstalled:
    def test_start_raises_import_error(self, tmp_path):
        with patch("src.audio_capture.pyaudio", None):
            capture = make_capture(tmp_path)
            with pytest.raises(ImportError, match="pyaudio"):
                capture.start(str(tmp_path / "out.wav"))


# ---------------------------------------------------------------------------
# TestDeviceDiscovery
# ---------------------------------------------------------------------------

class TestDeviceDiscovery:
    def _pa_with(self, devices: list[dict]) -> MagicMock:
        pa = MagicMock()
        pa.get_device_count.return_value = len(devices)
        pa.get_device_info_by_index.side_effect = _device_lookup(devices)
        return pa

    def test_finds_blackhole_by_exact_name(self):
        pa = self._pa_with(DEFAULT_DEVICES)
        assert AudioCapture(CaptureConfig()).find_device_index(pa) == 1

    def test_raises_device_not_found(self):
        pa = self._pa_with([
            {"name": "Built-in Microphone", "index": 0},
            {"name": "Built-in Output",     "index": 1},
        ])
        with pytest.raises(DeviceNotFoundError, match="BlackHole 2ch"):
            AudioCapture(CaptureConfig()).find_device_index(pa)

    def test_partial_name_match(self):
        pa = self._pa_with(DEFAULT_DEVICES)
        capture = AudioCapture(CaptureConfig(device_name="BlackHole"))
        assert capture.find_device_index(pa) == 1

    def test_name_match_is_case_insensitive(self):
        pa = self._pa_with(DEFAULT_DEVICES)
        capture = AudioCapture(CaptureConfig(device_name="blackhole 2ch"))
        assert capture.find_device_index(pa) == 1

    def test_returns_index_from_device_info(self):
        """index field from device info dict, not the loop counter."""
        devices = [
            {"name": "Other", "index": 10},
            {"name": "BlackHole 2ch", "index": 42},
        ]
        pa = self._pa_with(devices)
        assert AudioCapture(CaptureConfig()).find_device_index(pa) == 42

    def test_device_not_found_is_correct_type(self):
        pa = self._pa_with([{"name": "Other", "index": 0}])
        with pytest.raises(DeviceNotFoundError):
            AudioCapture(CaptureConfig()).find_device_index(pa)


# ---------------------------------------------------------------------------
# TestRecordLoop — tested synchronously, no threads
# ---------------------------------------------------------------------------

class TestRecordLoop:
    def test_no_reads_when_stop_event_preset(self, tmp_path):
        stop_event = threading.Event()
        stop_event.set()
        mock_stream = MagicMock()
        wf = open_wav_for_writing(str(tmp_path / "empty.wav"))
        AudioCapture(CaptureConfig())._record_loop(mock_stream, wf, stop_event)
        wf.close()
        mock_stream.read.assert_not_called()

    def test_reads_chunks_until_stop_event(self, tmp_path):
        stop_event = threading.Event()
        calls = [0]

        def fake_read(chunk_size, exception_on_overflow):
            calls[0] += 1
            if calls[0] >= 3:
                stop_event.set()
            return b"\x01\x02" * (chunk_size // 2)

        mock_stream = MagicMock()
        mock_stream.read.side_effect = fake_read

        wf = open_wav_for_writing(str(tmp_path / "frames.wav"))
        AudioCapture(CaptureConfig())._record_loop(mock_stream, wf, stop_event)
        wf.close()

        assert calls[0] == 3

    def test_frames_written_to_wav(self, tmp_path):
        stop_event = threading.Event()
        chunk = b"\x7f\x80" * 512  # 1024 bytes of non-silence

        def fake_read(chunk_size, exception_on_overflow):
            stop_event.set()  # stop after first read
            return chunk

        mock_stream = MagicMock()
        mock_stream.read.side_effect = fake_read

        wav_path = str(tmp_path / "data.wav")
        wf = open_wav_for_writing(wav_path)
        AudioCapture(CaptureConfig())._record_loop(mock_stream, wf, stop_event)
        wf.close()

        with wave.open(wav_path, "rb") as check:
            assert check.getnframes() > 0

    def test_read_called_with_exception_on_overflow_false(self, tmp_path):
        stop_event = threading.Event()

        def fake_read(chunk_size, exception_on_overflow):
            assert exception_on_overflow is False
            stop_event.set()
            return b"\x00" * chunk_size

        mock_stream = MagicMock()
        mock_stream.read.side_effect = fake_read
        wf = open_wav_for_writing(str(tmp_path / "overflow.wav"))
        AudioCapture(CaptureConfig())._record_loop(mock_stream, wf, stop_event)
        wf.close()


# ---------------------------------------------------------------------------
# TestLoadFromConfig
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_output_dir_from_yaml(self):
        capture = load_audio_capture_from_config("config/config.yaml")
        assert capture.config.output_dir == "output/captures"

    def test_device_name_from_yaml(self):
        capture = load_audio_capture_from_config("config/config.yaml")
        assert capture.config.device_name == "BlackHole 2ch"

    def test_sample_rate_from_yaml(self):
        capture = load_audio_capture_from_config("config/config.yaml")
        assert capture.config.sample_rate == 44100

    def test_output_dir_override(self):
        capture = load_audio_capture_from_config(
            "config/config.yaml", output_dir="/override/captures"
        )
        assert capture.config.output_dir == "/override/captures"

    def test_missing_section_uses_defaults(self, tmp_path):
        cfg_path = tmp_path / "min.yaml"
        cfg_path.write_text("app:\n  log_level: INFO\n", encoding="utf-8")
        capture = load_audio_capture_from_config(str(cfg_path))
        assert capture.config.device_name == "BlackHole 2ch"
        assert capture.config.sample_rate == 44100
        assert capture.config.output_dir == "output/captures"
