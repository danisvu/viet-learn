import shutil
import subprocess
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.models import SubtitleEntry
from src.tts_engine import TTSEngine, TTSConfig, AudioClip


PIPER_AVAILABLE = shutil.which("piper") is not None or Path("venv/bin/piper").exists()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_vi_entry(index: int, text: str, duration: float = 3.0) -> SubtitleEntry:
    return SubtitleEntry(index=index, start_time=float(index * 4), end_time=float(index * 4 + duration), text=text)


DEFAULT_CONFIG = TTSConfig(
    model_path="piper_models/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx",
    speed=1.0,
)


def _make_mock_piper(wav_path_arg_index: int = -1):
    """Return a mock for subprocess.run that writes a tiny valid WAV file."""
    import struct, wave as wave_mod

    def fake_run(cmd, **kwargs):
        # Find --output_file path from cmd list
        try:
            idx = cmd.index("--output_file")
            out_path = cmd[idx + 1]
        except (ValueError, IndexError):
            out_path = None

        if out_path:
            # Write a minimal valid WAV: 22050 Hz, mono, 0.1s silence
            n_frames = 2205
            with wave_mod.open(out_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * n_frames)

        result = MagicMock()
        result.returncode = 0
        return result

    return fake_run


# ---------------------------------------------------------------------------
# Tests: AudioClip dataclass
# ---------------------------------------------------------------------------

class TestAudioClip:
    def test_fields_exist(self):
        clip = AudioClip(
            file_path="/tmp/clip_001.wav",
            actual_duration=2.5,
            target_duration=3.0,
            index=1,
        )
        assert clip.file_path == "/tmp/clip_001.wav"
        assert clip.actual_duration == 2.5
        assert clip.target_duration == 3.0
        assert clip.index == 1


# ---------------------------------------------------------------------------
# Tests: TTSConfig
# ---------------------------------------------------------------------------

class TestTTSConfig:
    def test_default_speed(self):
        cfg = TTSConfig(model_path="model.onnx")
        assert cfg.speed == 1.0

    def test_custom_speed(self):
        cfg = TTSConfig(model_path="model.onnx", speed=1.2)
        assert cfg.speed == 1.2


# ---------------------------------------------------------------------------
# Tests: generate_clip (mocked piper)
# ---------------------------------------------------------------------------

class TestGenerateClipMocked:
    def test_returns_audio_clip(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert isinstance(clip, AudioClip)

    def test_clip_file_exists(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert Path(clip.file_path).exists()

    def test_clip_filename_contains_index(self, tmp_path):
        entry = make_vi_entry(7, "Học máy")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert "007" in Path(clip.file_path).name or "7" in Path(clip.file_path).name

    def test_clip_actual_duration_positive(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert clip.actual_duration > 0

    def test_clip_target_duration_matches_entry(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào", duration=4.5)
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert clip.target_duration == pytest.approx(4.5)

    def test_clip_index_matches_entry(self, tmp_path):
        entry = make_vi_entry(42, "Kiểm tra")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert clip.index == 42

    def test_piper_called_with_model_path(self, tmp_path):
        entry = make_vi_entry(1, "Hello")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()) as mock_run:
            engine.generate_clip(entry)
        cmd = mock_run.call_args[0][0]
        assert DEFAULT_CONFIG.model_path in cmd

    def test_piper_receives_text_via_stdin(self, tmp_path):
        entry = make_vi_entry(1, "Học sâu")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()) as mock_run:
            engine.generate_clip(entry)
        kwargs = mock_run.call_args[1]
        assert kwargs.get("input") == "Học sâu"

    def test_output_file_is_wav(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clip = engine.generate_clip(entry)
        assert clip.file_path.endswith(".wav")


# ---------------------------------------------------------------------------
# Tests: generate_all (mocked piper)
# ---------------------------------------------------------------------------

class TestGenerateAllMocked:
    def test_empty_list_returns_empty(self, tmp_path):
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        result = engine.generate_all([])
        assert result == []

    def test_returns_one_clip_per_entry(self, tmp_path):
        entries = [make_vi_entry(i, f"Câu số {i}") for i in range(1, 4)]
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clips = engine.generate_all(entries)
        assert len(clips) == 3

    def test_clips_have_unique_file_paths(self, tmp_path):
        entries = [make_vi_entry(i, f"Câu {i}") for i in range(1, 4)]
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clips = engine.generate_all(entries)
        paths = [c.file_path for c in clips]
        assert len(set(paths)) == len(paths)

    def test_progress_callback_called_for_each(self, tmp_path):
        entries = [make_vi_entry(i, f"Câu {i}") for i in range(1, 4)]
        progress_calls = []

        def on_progress(current, total, clip):
            progress_calls.append((current, total))

        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            engine.generate_all(entries, progress_callback=on_progress)

        assert progress_calls == [(1, 3), (2, 3), (3, 3)]

    def test_all_output_files_exist(self, tmp_path):
        entries = [make_vi_entry(i, f"Từ {i}") for i in range(1, 3)]
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clips = engine.generate_all(entries)
        for clip in clips:
            assert Path(clip.file_path).exists()

    def test_uses_tempdir_when_output_dir_not_given(self):
        entries = [make_vi_entry(1, "Xin chào")]
        engine = TTSEngine(config=DEFAULT_CONFIG)
        with patch("subprocess.run", side_effect=_make_mock_piper()):
            clips = engine.generate_all(entries)
        assert Path(clips[0].file_path).exists()

    def test_piper_failure_raises(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào")
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))

        def fail_run(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 1
            r.stderr = "piper error"
            return r

        with patch("subprocess.run", side_effect=fail_run):
            with pytest.raises(RuntimeError, match="Piper"):
                engine.generate_clip(entry)


# ---------------------------------------------------------------------------
# Tests: integration with real Piper (skip if not available)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not PIPER_AVAILABLE, reason="piper not installed")
class TestGenerateClipReal:
    def test_wav_file_created(self, tmp_path):
        entry = make_vi_entry(1, "Xin chào", duration=2.0)
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        clip = engine.generate_clip(entry)
        assert Path(clip.file_path).exists()
        assert Path(clip.file_path).stat().st_size > 0

    def test_actual_duration_positive(self, tmp_path):
        entry = make_vi_entry(1, "Học máy", duration=2.0)
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        clip = engine.generate_clip(entry)
        assert clip.actual_duration > 0

    def test_target_duration_set_correctly(self, tmp_path):
        entry = make_vi_entry(1, "Trí tuệ nhân tạo", duration=3.5)
        engine = TTSEngine(config=DEFAULT_CONFIG, output_dir=str(tmp_path))
        clip = engine.generate_clip(entry)
        assert clip.target_duration == pytest.approx(3.5)
