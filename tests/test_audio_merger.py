import wave
import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import numpy as np
import soundfile as sf

from src.tts_engine import AudioClip
from src.audio_merger import AudioMerger, MergerConfig, assemble_audio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SR = 22050


def make_wav(path: str, duration: float, frequency: float = 0.0) -> None:
    n = int(duration * SR)
    if frequency > 0:
        t = np.linspace(0, duration, n, endpoint=False)
        audio = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
    else:
        audio = np.zeros(n, dtype=np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(audio.tobytes())


def make_clip(tmp_path, index: int, start: float, duration: float, freq: float = 440.0) -> AudioClip:
    p = tmp_path / f"clip_{index:04d}.wav"
    make_wav(str(p), duration, frequency=freq)
    return AudioClip(
        file_path=str(p),
        actual_duration=duration,
        target_duration=duration,
        index=index,
        start_time=start,
    )


DEFAULT_CONFIG = MergerConfig(original_volume=0.15, vi_volume=1.0)


# ---------------------------------------------------------------------------
# Tests: MergerConfig
# ---------------------------------------------------------------------------

class TestMergerConfig:
    def test_defaults(self):
        cfg = MergerConfig()
        assert cfg.original_volume == pytest.approx(0.15)
        assert cfg.vi_volume == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Tests: assemble_audio — clips placed at correct positions
# ---------------------------------------------------------------------------

class TestAssembleAudio:
    def test_returns_output_path(self, tmp_path):
        clips = [make_clip(tmp_path, 1, start=0.0, duration=1.0)]
        out = str(tmp_path / "assembled.wav")
        result = assemble_audio(clips, total_duration=3.0, output_path=out)
        assert result == out

    def test_output_file_created(self, tmp_path):
        clips = [make_clip(tmp_path, 1, start=0.0, duration=1.0)]
        out = str(tmp_path / "assembled.wav")
        assemble_audio(clips, total_duration=3.0, output_path=out)
        assert Path(out).exists()

    def test_output_duration_matches_total(self, tmp_path):
        clips = [make_clip(tmp_path, 1, start=1.0, duration=1.0)]
        out = str(tmp_path / "assembled.wav")
        assemble_audio(clips, total_duration=5.0, output_path=out)
        info = sf.info(out)
        actual = info.frames / info.samplerate
        assert abs(actual - 5.0) < 0.05

    def test_clip_placed_at_start_time(self, tmp_path):
        # Clip at 1.0s with 440Hz sine — verify samples at 1.0s are non-zero
        clips = [make_clip(tmp_path, 1, start=1.0, duration=0.5, freq=440.0)]
        out = str(tmp_path / "assembled.wav")
        assemble_audio(clips, total_duration=3.0, output_path=out)
        data, sr = sf.read(out, dtype="int16")
        pos = int(1.0 * sr)
        assert np.any(data[pos : pos + int(0.2 * sr)] != 0)

    def test_gap_before_clip_is_silence(self, tmp_path):
        # Clip starts at 2.0s — first 1.5s should be silence
        clips = [make_clip(tmp_path, 1, start=2.0, duration=0.5, freq=440.0)]
        out = str(tmp_path / "assembled.wav")
        assemble_audio(clips, total_duration=4.0, output_path=out)
        data, sr = sf.read(out, dtype="int16")
        pre_gap = data[: int(1.5 * sr)]
        assert np.all(pre_gap == 0)

    def test_multiple_clips_assembled(self, tmp_path):
        clips = [
            make_clip(tmp_path, 1, start=0.0, duration=1.0, freq=220.0),
            make_clip(tmp_path, 2, start=2.0, duration=1.0, freq=880.0),
        ]
        out = str(tmp_path / "assembled.wav")
        assemble_audio(clips, total_duration=4.0, output_path=out)
        info = sf.info(out)
        assert abs(info.frames / info.samplerate - 4.0) < 0.05

    def test_empty_clips_creates_silence(self, tmp_path):
        out = str(tmp_path / "assembled.wav")
        assemble_audio([], total_duration=2.0, output_path=out)
        data, sr = sf.read(out, dtype="int16")
        assert np.all(data == 0)
        assert abs(len(data) / sr - 2.0) < 0.05

    def test_output_directory_created(self, tmp_path):
        clips = [make_clip(tmp_path, 1, start=0.0, duration=1.0)]
        out = str(tmp_path / "subdir" / "assembled.wav")
        assemble_audio(clips, total_duration=2.0, output_path=out)
        assert Path(out).exists()


# ---------------------------------------------------------------------------
# Tests: AudioMerger.merge_video — FFmpeg command (mocked)
# ---------------------------------------------------------------------------

class TestMergeVideoCommand:
    def _run_merge(self, tmp_path, mock_run):
        video = str(tmp_path / "video.mp4")
        vi_audio = str(tmp_path / "vi.wav")
        output = str(tmp_path / "output.mp4")
        Path(video).touch()
        Path(vi_audio).touch()
        merger = AudioMerger(config=DEFAULT_CONFIG)
        merger.merge_video(
            video_path=video,
            vi_audio_path=vi_audio,
            output_path=output,
        )
        return mock_run.call_args[0][0], output

    def test_ffmpeg_called(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, _ = self._run_merge(tmp_path, mock_run)
        assert cmd[0] == "ffmpeg"

    def test_ffmpeg_input_video(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, _ = self._run_merge(tmp_path, mock_run)
        assert str(tmp_path / "video.mp4") in cmd

    def test_ffmpeg_input_vi_audio(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, _ = self._run_merge(tmp_path, mock_run)
        assert str(tmp_path / "vi.wav") in cmd

    def test_ffmpeg_output_path(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, output = self._run_merge(tmp_path, mock_run)
        assert output in cmd

    def test_ffmpeg_uses_original_volume(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, _ = self._run_merge(tmp_path, mock_run)
        cmd_str = " ".join(cmd)
        assert "0.15" in cmd_str

    def test_ffmpeg_video_stream_copied(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cmd, _ = self._run_merge(tmp_path, mock_run)
        assert "-c:v" in cmd
        assert "copy" in cmd

    def test_ffmpeg_failure_raises(self, tmp_path):
        video = str(tmp_path / "v.mp4")
        vi_audio = str(tmp_path / "a.wav")
        Path(video).touch()
        Path(vi_audio).touch()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
            merger = AudioMerger(config=DEFAULT_CONFIG)
            with pytest.raises(RuntimeError, match="FFmpeg"):
                merger.merge_video(video, vi_audio, str(tmp_path / "out.mp4"))


# ---------------------------------------------------------------------------
# Tests: export_mp3
# ---------------------------------------------------------------------------

class TestExportMp3:
    def test_ffmpeg_called_for_mp3(self, tmp_path):
        vi_audio = str(tmp_path / "vi.wav")
        mp3_out = str(tmp_path / "vi.mp3")
        Path(vi_audio).touch()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            merger = AudioMerger(config=DEFAULT_CONFIG)
            merger.export_mp3(vi_audio_path=vi_audio, output_path=mp3_out)
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd[0]
        assert mp3_out in cmd

    def test_mp3_output_has_mp3_extension(self, tmp_path):
        vi_audio = str(tmp_path / "vi.wav")
        mp3_out = str(tmp_path / "out.mp3")
        Path(vi_audio).touch()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            merger = AudioMerger(config=DEFAULT_CONFIG)
            merger.export_mp3(vi_audio, mp3_out)
        assert mp3_out.endswith(".mp3")


# ---------------------------------------------------------------------------
# Tests: load from config
# ---------------------------------------------------------------------------

class TestLoadFromConfig:
    def test_loads_volumes_from_yaml(self):
        from src.audio_merger import load_merger_from_config
        merger = load_merger_from_config("config/config.yaml")
        assert merger.config.original_volume == pytest.approx(0.15)
        assert merger.config.vi_volume == pytest.approx(1.0)
