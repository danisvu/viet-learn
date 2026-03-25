"""Tests for src/whisper_stt.py — TDD suite (all pywhispercpp calls mocked)."""
from __future__ import annotations

import wave
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.models import SubtitleEntry
from src.whisper_stt import (
    STTResult,
    WhisperConfig,
    WhisperSTT,
    load_whisper_stt_from_config,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_segment(text: str, t0: int, t1: int) -> MagicMock:
    """Build a mock whisper.cpp Segment (t0/t1 in 10ms units)."""
    seg = MagicMock()
    seg.text = text
    seg.t0 = t0
    seg.t1 = t1
    return seg


def make_wav(path: str, duration_s: float = 1.0, sample_rate: int = 16000) -> None:
    """Write a minimal valid WAV file for input validation tests."""
    import struct
    n_frames = int(duration_s * sample_rate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)


@pytest.fixture
def mock_whisper_model():
    """Patch src.whisper_stt.WhisperModel with a mock class."""
    with patch("src.whisper_stt.WhisperModel") as MockModel:
        mock_instance = MagicMock()
        MockModel.return_value = mock_instance
        mock_instance.transcribe.return_value = []  # default: no segments
        yield MockModel, mock_instance


def make_stt(tmp_path: Path, **cfg_kwargs) -> WhisperSTT:
    cfg_kwargs.setdefault("output_dir", str(tmp_path / "stt"))
    return WhisperSTT(WhisperConfig(**cfg_kwargs))


def transcribe(stt: WhisperSTT, audio_path: str, output_path: str | None = None) -> STTResult:
    return stt.transcribe(audio_path, output_path=output_path)


# ---------------------------------------------------------------------------
# TestWhisperConfig
# ---------------------------------------------------------------------------

class TestWhisperConfig:
    def test_default_model(self):
        assert WhisperConfig().model == "large-v3-turbo"

    def test_default_model_dir(self):
        assert WhisperConfig().model_dir == "whisper_models"

    def test_default_n_threads(self):
        assert WhisperConfig().n_threads == 4

    def test_default_language(self):
        assert WhisperConfig().language == "en"

    def test_default_output_dir(self):
        assert WhisperConfig().output_dir == "output/stt"

    def test_custom_values(self):
        cfg = WhisperConfig(
            model="medium",
            model_dir="/models",
            n_threads=8,
            language="vi",
            output_dir="/out",
        )
        assert cfg.model == "medium"
        assert cfg.model_dir == "/models"
        assert cfg.n_threads == 8
        assert cfg.language == "vi"
        assert cfg.output_dir == "/out"


# ---------------------------------------------------------------------------
# TestSTTResult
# ---------------------------------------------------------------------------

class TestSTTResult:
    def test_fields_exist(self, tmp_path):
        r = STTResult(
            srt_path=str(tmp_path / "out.srt"),
            entries=[],
            audio_path=str(tmp_path / "audio.wav"),
        )
        assert r.srt_path.endswith(".srt")
        assert r.entries == []
        assert r.audio_path.endswith(".wav")

    def test_entries_is_list(self, tmp_path):
        entries = [SubtitleEntry(1, 0.0, 1.0, "Hello")]
        r = STTResult(srt_path="/x.srt", entries=entries, audio_path="/a.wav")
        assert isinstance(r.entries, list)
        assert len(r.entries) == 1


# ---------------------------------------------------------------------------
# TestTranscribe
# ---------------------------------------------------------------------------

class TestTranscribe:
    def test_returns_stt_result(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert isinstance(result, STTResult)

    def test_srt_path_in_result(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert result.srt_path.endswith(".srt")

    def test_entries_list_in_result(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert isinstance(result.entries, list)

    def test_audio_path_preserved_in_result(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert result.audio_path == str(wav)

    def test_srt_file_created_on_disk(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert Path(result.srt_path).exists()

    def test_model_transcribe_called_with_audio_path(self, tmp_path, mock_whisper_model):
        MockModel, mock_instance = mock_whisper_model
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        make_stt(tmp_path).transcribe(str(wav))
        mock_instance.transcribe.assert_called_once_with(str(wav))

    def test_missing_audio_raises_file_not_found(self, tmp_path, mock_whisper_model):
        missing = str(tmp_path / "ghost.wav")
        with pytest.raises(FileNotFoundError, match="ghost.wav"):
            make_stt(tmp_path).transcribe(missing)


# ---------------------------------------------------------------------------
# TestOutputPathResolution
# ---------------------------------------------------------------------------

class TestOutputPathResolution:
    def test_default_path_uses_audio_stem(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "lecture01.wav"
        make_wav(str(wav))
        stt = WhisperSTT(WhisperConfig(output_dir=str(tmp_path / "stt")))
        result = stt.transcribe(str(wav))
        assert Path(result.srt_path).stem == "lecture01"

    def test_default_path_has_srt_extension(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        result = make_stt(tmp_path).transcribe(str(wav))
        assert result.srt_path.endswith(".srt")

    def test_default_path_is_inside_output_dir(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        out_dir = str(tmp_path / "stt_out")
        stt = WhisperSTT(WhisperConfig(output_dir=out_dir))
        result = stt.transcribe(str(wav))
        assert result.srt_path.startswith(out_dir)

    def test_custom_output_path_respected(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        custom = str(tmp_path / "my" / "custom.srt")
        result = make_stt(tmp_path).transcribe(str(wav), output_path=custom)
        assert result.srt_path == custom

    def test_output_dir_created_if_missing(self, tmp_path, mock_whisper_model):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        out_dir = tmp_path / "deep" / "nested" / "stt"
        stt = WhisperSTT(WhisperConfig(output_dir=str(out_dir)))
        stt.transcribe(str(wav))
        assert out_dir.exists()


# ---------------------------------------------------------------------------
# TestSegmentsToEntries
# ---------------------------------------------------------------------------

class TestSegmentsToEntries:
    """Test _segments_to_entries in isolation — no file I/O needed."""

    def _convert(self, segments) -> list[SubtitleEntry]:
        return WhisperSTT(WhisperConfig())._segments_to_entries(segments)

    def test_index_starts_at_one(self):
        segs = [make_segment("Hello", t0=0, t1=100)]
        entries = self._convert(segs)
        assert entries[0].index == 1

    def test_sequential_indices(self):
        segs = [
            make_segment("One",   t0=0,   t1=100),
            make_segment("Two",   t0=100, t1=200),
            make_segment("Three", t0=200, t1=300),
        ]
        entries = self._convert(segs)
        assert [e.index for e in entries] == [1, 2, 3]

    def test_t0_converted_to_seconds(self):
        segs = [make_segment("Hi", t0=100, t1=200)]  # 100 × 10ms = 1.0 s
        entries = self._convert(segs)
        assert entries[0].start_time == pytest.approx(1.0)

    def test_t1_converted_to_seconds(self):
        segs = [make_segment("Hi", t0=0, t1=350)]  # 350 × 10ms = 3.5 s
        entries = self._convert(segs)
        assert entries[0].end_time == pytest.approx(3.5)

    def test_fractional_seconds_preserved(self):
        segs = [make_segment("Hi", t0=75, t1=125)]  # 0.75 s → 1.25 s
        entries = self._convert(segs)
        assert entries[0].start_time == pytest.approx(0.75)
        assert entries[0].end_time == pytest.approx(1.25)

    def test_text_stripped(self):
        segs = [make_segment("  Hello world  ", t0=0, t1=100)]
        entries = self._convert(segs)
        assert entries[0].text == "Hello world"

    def test_empty_text_segment_filtered(self):
        segs = [
            make_segment("Hello", t0=0,   t1=100),
            make_segment("",      t0=100, t1=200),   # empty → skip
            make_segment("  ",    t0=200, t1=300),   # whitespace-only → skip
            make_segment("World", t0=300, t1=400),
        ]
        entries = self._convert(segs)
        assert len(entries) == 2
        assert entries[0].text == "Hello"
        assert entries[1].text == "World"

    def test_empty_segment_list_returns_empty(self):
        assert self._convert([]) == []

    def test_single_segment_returns_list_of_one(self):
        segs = [make_segment("One", t0=0, t1=100)]
        assert len(self._convert(segs)) == 1

    def test_indices_resequenced_after_empty_filter(self):
        """After filtering empties, remaining indices must be 1, 2, ... (no gaps)."""
        segs = [
            make_segment("A", t0=0,   t1=100),
            make_segment("",  t0=100, t1=200),
            make_segment("B", t0=200, t1=300),
        ]
        entries = self._convert(segs)
        assert entries[0].index == 1
        assert entries[1].index == 2


# ---------------------------------------------------------------------------
# TestSrtContent
# ---------------------------------------------------------------------------

class TestSrtContent:
    """Verify the SRT file written to disk has correct format."""

    def _write_and_read(self, tmp_path: Path, segments) -> str:
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        with patch("src.whisper_stt.WhisperModel") as MockModel:
            MockModel.return_value.transcribe.return_value = segments
            stt = WhisperSTT(WhisperConfig(output_dir=str(tmp_path / "stt")))
            result = stt.transcribe(str(wav))
        return Path(result.srt_path).read_text(encoding="utf-8")

    def test_srt_has_index_numbers(self, tmp_path):
        content = self._write_and_read(tmp_path, [
            make_segment("Hello", t0=0, t1=100),
        ])
        assert "1\n" in content

    def test_srt_has_arrow_separator(self, tmp_path):
        content = self._write_and_read(tmp_path, [
            make_segment("Hi", t0=0, t1=100),
        ])
        assert " --> " in content

    def test_srt_timestamps_use_comma_not_dot(self, tmp_path):
        content = self._write_and_read(tmp_path, [
            make_segment("Hi", t0=100, t1=350),
        ])
        assert "00:00:01,000" in content
        assert "00:00:03,500" in content

    def test_srt_contains_text(self, tmp_path):
        content = self._write_and_read(tmp_path, [
            make_segment("Deep learning is fun", t0=0, t1=200),
        ])
        assert "Deep learning is fun" in content

    def test_srt_multiple_entries_separated_by_blank_line(self, tmp_path):
        content = self._write_and_read(tmp_path, [
            make_segment("First",  t0=0,   t1=100),
            make_segment("Second", t0=200, t1=300),
        ])
        assert "1\n" in content
        assert "2\n" in content
        # Entries separated by blank line
        assert "\n\n" in content

    def test_empty_segments_produce_empty_srt(self, tmp_path):
        content = self._write_and_read(tmp_path, [])
        assert content == ""


# ---------------------------------------------------------------------------
# TestModelLoading
# ---------------------------------------------------------------------------

class TestModelLoading:
    def test_model_not_loaded_at_init(self, tmp_path):
        with patch("src.whisper_stt.WhisperModel") as MockModel:
            WhisperSTT(WhisperConfig(output_dir=str(tmp_path)))
            MockModel.assert_not_called()

    def test_model_loaded_on_first_transcribe(self, tmp_path, mock_whisper_model):
        MockModel, _ = mock_whisper_model
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        make_stt(tmp_path).transcribe(str(wav))
        MockModel.assert_called_once()

    def test_model_reused_on_second_transcribe(self, tmp_path, mock_whisper_model):
        MockModel, _ = mock_whisper_model
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        stt = make_stt(tmp_path)
        stt.transcribe(str(wav))
        stt.transcribe(str(wav))
        # Constructor called only once despite two transcribe() calls
        assert MockModel.call_count == 1

    def test_model_constructed_with_model_name(self, tmp_path, mock_whisper_model):
        MockModel, _ = mock_whisper_model
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        WhisperSTT(WhisperConfig(model="medium", output_dir=str(tmp_path))).transcribe(str(wav))
        args, kwargs = MockModel.call_args
        assert args[0] == "medium" or kwargs.get("model") == "medium"

    def test_model_constructed_with_model_dir(self, tmp_path, mock_whisper_model):
        MockModel, _ = mock_whisper_model
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        WhisperSTT(WhisperConfig(model_dir="/my/models", output_dir=str(tmp_path))).transcribe(str(wav))
        _, kwargs = MockModel.call_args
        assert kwargs.get("models_dir") == "/my/models"

    def test_whisper_not_installed_raises_import_error(self, tmp_path):
        wav = tmp_path / "audio.wav"
        make_wav(str(wav))
        with patch("src.whisper_stt.WhisperModel", None):
            with pytest.raises(ImportError, match="pywhispercpp"):
                make_stt(tmp_path).transcribe(str(wav))


# ---------------------------------------------------------------------------
# TestLoadFromConfig
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_model_from_yaml(self):
        stt = load_whisper_stt_from_config("config/config.yaml")
        assert stt.config.model == "large-v3-turbo"

    def test_model_dir_from_yaml(self):
        stt = load_whisper_stt_from_config("config/config.yaml")
        assert stt.config.model_dir == "whisper_models"

    def test_language_from_yaml(self):
        stt = load_whisper_stt_from_config("config/config.yaml")
        assert stt.config.language == "en"

    def test_output_dir_from_yaml(self):
        stt = load_whisper_stt_from_config("config/config.yaml")
        assert stt.config.output_dir == "output/stt"

    def test_output_dir_override(self):
        stt = load_whisper_stt_from_config(
            "config/config.yaml", output_dir="/override/stt"
        )
        assert stt.config.output_dir == "/override/stt"

    def test_missing_section_uses_defaults(self, tmp_path):
        cfg_path = tmp_path / "min.yaml"
        cfg_path.write_text("app:\n  log_level: INFO\n", encoding="utf-8")
        stt = load_whisper_stt_from_config(str(cfg_path))
        assert stt.config.model == "large-v3-turbo"
        assert stt.config.n_threads == 4
        assert stt.config.output_dir == "output/stt"
