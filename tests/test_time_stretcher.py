import wave
import struct
import pytest
from pathlib import Path

import soundfile as sf
import numpy as np

from src.tts_engine import AudioClip
from src.time_stretcher import (
    TimeStretcher,
    StretchConfig,
    StretchResult,
    StretchAction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOLERANCE = 0.05  # seconds — acceptable duration error after stretch


def make_wav(path: str, duration: float, sample_rate: int = 22050) -> None:
    """Write a WAV file of `duration` seconds filled with silence."""
    n_frames = int(duration * sample_rate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


def make_clip(tmp_path, actual_duration: float, target_duration: float, index: int = 1) -> AudioClip:
    wav = tmp_path / f"clip_{index:04d}.wav"
    make_wav(str(wav), actual_duration)
    return AudioClip(
        file_path=str(wav),
        actual_duration=actual_duration,
        target_duration=target_duration,
        index=index,
    )


def measure_duration(path: str) -> float:
    info = sf.info(path)
    return info.frames / info.samplerate


DEFAULT_CONFIG = StretchConfig(max_speed_ratio=1.6, min_speed_ratio=0.75)


# ---------------------------------------------------------------------------
# Tests: StretchConfig
# ---------------------------------------------------------------------------

class TestStretchConfig:
    def test_default_limits(self):
        cfg = StretchConfig()
        assert cfg.max_speed_ratio == 1.6
        assert cfg.min_speed_ratio == 0.75

    def test_custom_limits(self):
        cfg = StretchConfig(max_speed_ratio=2.0, min_speed_ratio=0.5)
        assert cfg.max_speed_ratio == 2.0
        assert cfg.min_speed_ratio == 0.5


# ---------------------------------------------------------------------------
# Tests: StretchResult
# ---------------------------------------------------------------------------

class TestStretchResult:
    def test_stretch_action_has_expected_values(self):
        assert StretchAction.STRETCHED in StretchAction.__members__.values()
        assert StretchAction.PADDED in StretchAction.__members__.values()
        assert StretchAction.TOO_FAST in StretchAction.__members__.values()

    def test_result_fields(self, tmp_path):
        result = StretchResult(
            file_path=str(tmp_path / "out.wav"),
            action=StretchAction.STRETCHED,
            speed_ratio=1.2,
            warning=None,
        )
        assert result.speed_ratio == pytest.approx(1.2)
        assert result.warning is None


# ---------------------------------------------------------------------------
# Tests: ratio = 1.0 (no-op)
# ---------------------------------------------------------------------------

class TestRatioOne:
    def test_returns_stretch_result(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.0, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert isinstance(result, StretchResult)

    def test_output_file_created(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.0, target_duration=3.0)
        out = str(tmp_path / "out.wav")
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=out)
        assert Path(result.file_path).exists()


# ---------------------------------------------------------------------------
# Tests: ratio in normal range (0.75 – 1.6) → STRETCHED
# ---------------------------------------------------------------------------

class TestNormalRange:
    def test_ratio_1_2_action_is_stretched(self, tmp_path):
        # actual=3.6s, target=3.0s → ratio=1.2
        clip = make_clip(tmp_path, actual_duration=3.6, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.STRETCHED

    def test_ratio_1_2_output_duration_near_target(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.6, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        actual = measure_duration(result.file_path)
        assert abs(actual - 3.0) <= TOLERANCE

    def test_ratio_0_9_compress(self, tmp_path):
        # actual=2.7s, target=3.0s → ratio=0.9 (slow down slightly)
        clip = make_clip(tmp_path, actual_duration=2.7, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.STRETCHED
        actual = measure_duration(result.file_path)
        assert abs(actual - 3.0) <= TOLERANCE

    def test_ratio_at_max_boundary(self, tmp_path):
        # ratio = exactly 1.6 → still STRETCHED (inclusive)
        clip = make_clip(tmp_path, actual_duration=4.8, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.STRETCHED

    def test_ratio_at_min_boundary(self, tmp_path):
        # ratio = exactly 0.75 → still STRETCHED (inclusive)
        clip = make_clip(tmp_path, actual_duration=2.25, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.STRETCHED

    def test_speed_ratio_stored_in_result(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.6, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.speed_ratio == pytest.approx(1.2)

    def test_no_warning_in_normal_range(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.6, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.warning is None


# ---------------------------------------------------------------------------
# Tests: ratio > 1.6 → TOO_FAST warning
# ---------------------------------------------------------------------------

class TestTooFast:
    def test_ratio_2_0_action_is_too_fast(self, tmp_path):
        # actual=6.0s, target=3.0s → ratio=2.0
        clip = make_clip(tmp_path, actual_duration=6.0, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.TOO_FAST

    def test_too_fast_has_warning_message(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=6.0, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.warning is not None
        assert len(result.warning) > 0

    def test_too_fast_warning_mentions_options(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=6.0, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        warning_lower = result.warning.lower()
        # Warning phải nhắc đến 2 option: accept fast hoặc summarize
        assert any(w in warning_lower for w in ["accept", "fast", "speed"])
        assert any(w in warning_lower for w in ["summarize", "shorten", "shorter"])

    def test_too_fast_still_produces_output_file(self, tmp_path):
        # Module vẫn tạo output (fast audio) — caller quyết định dùng hay không
        clip = make_clip(tmp_path, actual_duration=6.0, target_duration=3.0)
        out = str(tmp_path / "out.wav")
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=out)
        assert Path(result.file_path).exists()

    def test_too_fast_speed_ratio_stored(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=6.0, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.speed_ratio == pytest.approx(2.0)

    def test_just_above_max_is_too_fast(self, tmp_path):
        # ratio = 1.61 → TOO_FAST
        clip = make_clip(tmp_path, actual_duration=4.83, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.TOO_FAST


# ---------------------------------------------------------------------------
# Tests: ratio < 0.75 → PADDED (pad silence)
# ---------------------------------------------------------------------------

class TestTooSlow:
    def test_ratio_0_5_action_is_padded(self, tmp_path):
        # actual=1.5s, target=3.0s → ratio=0.5
        clip = make_clip(tmp_path, actual_duration=1.5, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.PADDED

    def test_padded_output_duration_equals_target(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=1.5, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        actual = measure_duration(result.file_path)
        assert abs(actual - 3.0) <= TOLERANCE

    def test_padded_audio_starts_at_beginning(self, tmp_path):
        # Original audio (non-silent) should be at the start of padded output
        # Make a WAV with a non-zero sample, then verify first samples are non-zero
        wav_path = tmp_path / "src.wav"
        sample_rate = 22050
        duration = 1.0
        n_frames = int(duration * sample_rate)
        # Sine wave so it's clearly non-silent
        t = np.linspace(0, duration, n_frames, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        clip = AudioClip(
            file_path=str(wav_path),
            actual_duration=duration,
            target_duration=3.0,
            index=1,
        )
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        data, sr = sf.read(result.file_path)
        # First 0.5s should contain non-zero samples (the original audio)
        first_half = data[: int(0.5 * sr)]
        assert np.any(first_half != 0)

    def test_padded_silence_at_end(self, tmp_path):
        # After original audio ends, the tail should be silence
        wav_path = tmp_path / "src.wav"
        sample_rate = 22050
        duration = 1.0
        n_frames = int(duration * sample_rate)
        t = np.linspace(0, duration, n_frames, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

        clip = AudioClip(
            file_path=str(wav_path),
            actual_duration=duration,
            target_duration=3.0,
            index=1,
        )
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        data, sr = sf.read(result.file_path)
        # Last 1.5s should be silence (zeros)
        last_chunk = data[-int(1.5 * sr):]
        assert np.all(last_chunk == 0)

    def test_padded_no_warning(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=1.5, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.warning is None

    def test_just_below_min_is_padded(self, tmp_path):
        # ratio = 0.74 → PADDED
        clip = make_clip(tmp_path, actual_duration=2.22, target_duration=3.0)
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=str(tmp_path / "out.wav"))
        assert result.action == StretchAction.PADDED


# ---------------------------------------------------------------------------
# Tests: output path & directory
# ---------------------------------------------------------------------------

class TestOutputPath:
    def test_output_dir_created_if_missing(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.0, target_duration=3.0)
        out = str(tmp_path / "new_subdir" / "out.wav")
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=out)
        assert Path(result.file_path).exists()

    def test_result_file_path_matches_output_path(self, tmp_path):
        clip = make_clip(tmp_path, actual_duration=3.0, target_duration=3.0)
        out = str(tmp_path / "out.wav")
        ts = TimeStretcher(config=DEFAULT_CONFIG)
        result = ts.process(clip, output_path=out)
        assert result.file_path == out


# ---------------------------------------------------------------------------
# Tests: load from config
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_loads_limits_from_yaml(self):
        from src.time_stretcher import load_stretcher_from_config
        ts = load_stretcher_from_config("config/config.yaml")
        assert ts.config.max_speed_ratio == pytest.approx(1.6)
        assert ts.config.min_speed_ratio == pytest.approx(0.75)
