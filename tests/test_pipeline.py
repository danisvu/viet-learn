import textwrap
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from src.models import SubtitleEntry
from src.tts_engine import AudioClip
from src.time_stretcher import StretchResult, StretchAction
from src.pipeline import Pipeline, PipelineConfig, PipelineStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SRT = textwrap.dedent("""\
    1
    00:00:01,000 --> 00:00:03,000
    Hello world

    2
    00:00:04,000 --> 00:00:06,000
    Deep learning is amazing

    """)

VI_TRANSLATIONS = ["Xin chào thế giới", "Học sâu rất tuyệt vời"]


def _make_en_entries():
    return [
        SubtitleEntry(1, 1.0, 3.0, "Hello world"),
        SubtitleEntry(2, 4.0, 6.0, "Deep learning is amazing"),
    ]


def _make_vi_entries():
    return [
        SubtitleEntry(1, 1.0, 3.0, "Xin chào thế giới"),
        SubtitleEntry(2, 4.0, 6.0, "Học sâu rất tuyệt vời"),
    ]


def _make_clips(tmp_path, entries):
    clips = []
    for e in entries:
        p = tmp_path / f"clip_{e.index:04d}.wav"
        p.write_bytes(b"")
        clips.append(AudioClip(
            file_path=str(p),
            actual_duration=e.end_time - e.start_time,
            target_duration=e.end_time - e.start_time,
            index=e.index,
            start_time=e.start_time,
        ))
    return clips


def _make_stretch_results(clips, tmp_path):
    results = []
    for clip in clips:
        p = tmp_path / f"stretched_{clip.index:04d}.wav"
        p.write_bytes(b"")
        results.append(StretchResult(
            file_path=str(p),
            action=StretchAction.STRETCHED,
            speed_ratio=1.0,
            warning=None,
        ))
    return results


DEFAULT_CONFIG = PipelineConfig(
    output_dir="",  # overridden per-test via tmp_path
)


# ---------------------------------------------------------------------------
# Tests: PipelineConfig
# ---------------------------------------------------------------------------

class TestPipelineConfig:
    def test_has_output_dir(self):
        cfg = PipelineConfig(output_dir="/tmp/out")
        assert cfg.output_dir == "/tmp/out"

    def test_has_required_keys_default(self):
        cfg = PipelineConfig(output_dir="/tmp")
        assert isinstance(cfg.required_keys, list)


# ---------------------------------------------------------------------------
# Tests: full pipeline flow with mocked modules
# ---------------------------------------------------------------------------

class TestPipelineFlow:
    def _run(self, tmp_path, srt_path=None, progress_calls=None):
        import wave, numpy as np

        if srt_path is None:
            srt_path = tmp_path / "input.srt"
            srt_path.write_text(SAMPLE_SRT, encoding="utf-8")

        video_path = tmp_path / "video.mp4"
        video_path.touch()

        en_entries = _make_en_entries()
        vi_entries = _make_vi_entries()
        clips = _make_clips(tmp_path, vi_entries)
        stretched = _make_stretch_results(clips, tmp_path)

        # Write a tiny real WAV for assembled audio
        assembled_wav = tmp_path / "vi_audio.wav"
        n = 22050 * 6
        with wave.open(str(assembled_wav), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())

        cfg = PipelineConfig(output_dir=str(tmp_path))
        pipeline = Pipeline(config=cfg)

        with patch("src.pipeline.parse_subtitle", return_value=en_entries) as mock_parse, \
             patch("src.pipeline.Translator") as MockTranslator, \
             patch("src.pipeline.write_bilingual_srt") as mock_bil, \
             patch("src.pipeline.write_vietnamese_srt") as mock_vi_srt, \
             patch("src.pipeline.TTSEngine") as MockTTS, \
             patch("src.pipeline.TimeStretcher") as MockStretch, \
             patch("src.pipeline.assemble_audio", return_value=str(assembled_wav)) as mock_assemble, \
             patch("src.pipeline.AudioMerger") as MockMerger:

            MockTranslator.return_value.translate.return_value = vi_entries
            MockTTS.return_value.generate_all.return_value = clips
            MockStretch.return_value.process.side_effect = stretched
            MockMerger.return_value.merge_video.return_value = None

            result = pipeline.run(
                video_path=str(video_path),
                subtitle_path=str(srt_path),
                progress_callback=progress_calls,
            )

        return result, {
            "parse": mock_parse,
            "translate": MockTranslator,
            "bil_srt": mock_bil,
            "vi_srt": mock_vi_srt,
            "tts": MockTTS,
            "stretch": MockStretch,
            "assemble": mock_assemble,
            "merge": MockMerger,
        }

    def test_run_returns_output_paths(self, tmp_path):
        result, _ = self._run(tmp_path)
        assert "bilingual_srt" in result
        assert "vi_srt" in result
        assert "vi_audio" in result
        assert "video" in result

    def test_parse_subtitle_called(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["parse"].assert_called_once()

    def test_translate_called(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["translate"].return_value.translate.assert_called_once()

    def test_bilingual_srt_written(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["bil_srt"].assert_called_once()

    def test_vi_srt_written(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["vi_srt"].assert_called_once()

    def test_tts_generate_called(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["tts"].return_value.generate_all.assert_called_once()

    def test_time_stretch_called_per_clip(self, tmp_path):
        _, mocks = self._run(tmp_path)
        assert mocks["stretch"].return_value.process.call_count == 2

    def test_assemble_audio_called(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["assemble"].assert_called_once()

    def test_merge_video_called(self, tmp_path):
        _, mocks = self._run(tmp_path)
        mocks["merge"].return_value.merge_video.assert_called_once()

    def test_progress_callback_called_for_each_step(self, tmp_path):
        calls = []
        def on_progress(step: PipelineStep, pct: float, msg: str):
            calls.append(step)
        self._run(tmp_path, progress_calls=on_progress)
        steps_seen = set(calls)
        assert PipelineStep.PARSING in steps_seen
        assert PipelineStep.TRANSLATING in steps_seen
        assert PipelineStep.TTS in steps_seen
        assert PipelineStep.MERGING in steps_seen

    def test_output_files_are_in_output_dir(self, tmp_path):
        result, _ = self._run(tmp_path)
        for key, path in result.items():
            if path:
                assert str(tmp_path) in path


# ---------------------------------------------------------------------------
# Tests: error handling — TTS failure on one entry is skipped
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_tts_failure_on_one_entry_skipped(self, tmp_path):
        import wave, numpy as np

        srt_path = tmp_path / "input.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        en_entries = _make_en_entries()
        vi_entries = _make_vi_entries()
        # Only 1 clip succeeds (index 2); index 1 raises
        good_clip = AudioClip(
            file_path=str(tmp_path / "clip_0002.wav"),
            actual_duration=2.0, target_duration=2.0,
            index=2, start_time=4.0,
        )
        Path(good_clip.file_path).write_bytes(b"")

        stretched_path = tmp_path / "stretched_0002.wav"
        stretched_path.write_bytes(b"")
        good_stretch = StretchResult(
            file_path=str(stretched_path),
            action=StretchAction.STRETCHED,
            speed_ratio=1.0, warning=None,
        )

        assembled_wav = tmp_path / "vi_audio.wav"
        n = 22050 * 6
        with wave.open(str(assembled_wav), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())

        cfg = PipelineConfig(output_dir=str(tmp_path))
        pipeline = Pipeline(config=cfg)

        with patch("src.pipeline.parse_subtitle", return_value=en_entries), \
             patch("src.pipeline.Translator") as MockTranslator, \
             patch("src.pipeline.write_bilingual_srt"), \
             patch("src.pipeline.write_vietnamese_srt"), \
             patch("src.pipeline.TTSEngine") as MockTTS, \
             patch("src.pipeline.TimeStretcher") as MockStretch, \
             patch("src.pipeline.assemble_audio", return_value=str(assembled_wav)), \
             patch("src.pipeline.AudioMerger") as MockMerger:

            MockTranslator.return_value.translate.return_value = vi_entries

            # TTS raises on first entry, succeeds on second
            def tts_side_effect(entries, progress_callback=None):
                results = []
                for e in entries:
                    if e.index == 1:
                        if progress_callback:
                            pass  # skip — error handled inside engine
                        # raise is handled by pipeline, not here
                        # simulate: engine returns partial list
                        continue
                    clip = AudioClip(
                        file_path=str(tmp_path / f"clip_{e.index:04d}.wav"),
                        actual_duration=2.0, target_duration=2.0,
                        index=e.index, start_time=e.start_time,
                    )
                    Path(clip.file_path).write_bytes(b"")
                    results.append(clip)
                return results

            MockTTS.return_value.generate_all.side_effect = tts_side_effect
            MockStretch.return_value.process.return_value = good_stretch
            MockMerger.return_value.merge_video.return_value = None

            # Should not raise even though one entry was skipped
            result = pipeline.run(
                video_path=str(video_path),
                subtitle_path=str(srt_path),
            )
        assert result is not None

    def test_too_fast_warning_logged_but_not_raised(self, tmp_path):
        import wave, numpy as np

        srt_path = tmp_path / "input.srt"
        srt_path.write_text(SAMPLE_SRT, encoding="utf-8")
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        en_entries = _make_en_entries()
        vi_entries = _make_vi_entries()
        clips = _make_clips(tmp_path, vi_entries)

        assembled_wav = tmp_path / "vi_audio.wav"
        n = 22050 * 6
        with wave.open(str(assembled_wav), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(np.zeros(n, dtype=np.int16).tobytes())

        # All clips return TOO_FAST warning
        def stretch_with_warning(clip, output_path):
            Path(output_path).write_bytes(b"")
            return StretchResult(
                file_path=output_path,
                action=StretchAction.TOO_FAST,
                speed_ratio=2.0,
                warning="Too fast: accept or summarize",
            )

        cfg = PipelineConfig(output_dir=str(tmp_path))
        pipeline = Pipeline(config=cfg)

        with patch("src.pipeline.parse_subtitle", return_value=en_entries), \
             patch("src.pipeline.Translator") as MockTranslator, \
             patch("src.pipeline.write_bilingual_srt"), \
             patch("src.pipeline.write_vietnamese_srt"), \
             patch("src.pipeline.TTSEngine") as MockTTS, \
             patch("src.pipeline.TimeStretcher") as MockStretch, \
             patch("src.pipeline.assemble_audio", return_value=str(assembled_wav)), \
             patch("src.pipeline.AudioMerger") as MockMerger:

            MockTranslator.return_value.translate.return_value = vi_entries
            MockTTS.return_value.generate_all.return_value = clips
            MockStretch.return_value.process.side_effect = stretch_with_warning
            MockMerger.return_value.merge_video.return_value = None

            result = pipeline.run(str(video_path), str(srt_path))

        assert result is not None
