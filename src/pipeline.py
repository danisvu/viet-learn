from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from src.srt_parser import parse_subtitle
from src.translator import Translator, TranslatorConfig
from src.srt_writer import write_bilingual_srt, write_vietnamese_srt
from src.tts_engine import TTSEngine, TTSConfig
from src.time_stretcher import TimeStretcher, StretchConfig, StretchAction
from src.audio_merger import AudioMerger, MergerConfig, assemble_audio

logger = logging.getLogger(__name__)


class PipelineStep(str, Enum):
    PARSING = "parsing"
    TRANSLATING = "translating"
    WRITING_SRT = "writing_srt"
    TTS = "tts"
    STRETCHING = "stretching"
    ASSEMBLING = "assembling"
    MERGING = "merging"
    DONE = "done"


ProgressCallback = Callable[[PipelineStep, float, str], None]


@dataclass
class PipelineConfig:
    output_dir: str
    required_keys: list[str] = field(default_factory=list)
    translator: TranslatorConfig = field(default_factory=TranslatorConfig)
    tts: TTSConfig = field(default_factory=lambda: TTSConfig(
        model_path="piper_models/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx"
    ))
    stretch: StretchConfig = field(default_factory=StretchConfig)
    merger: MergerConfig = field(default_factory=MergerConfig)


class Pipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(
        self,
        video_path: str,
        subtitle_path: str,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, str]:
        out = Path(self.config.output_dir)
        out.mkdir(parents=True, exist_ok=True)

        stem = Path(video_path).stem

        def _progress(step: PipelineStep, pct: float, msg: str = ""):
            logger.info("[%s] %.0f%% %s", step.value, pct * 100, msg)
            if progress_callback:
                progress_callback(step, pct, msg)

        # ── Step 1: Parse ──────────────────────────────────────────────
        _progress(PipelineStep.PARSING, 0.0, subtitle_path)
        en_entries = parse_subtitle(subtitle_path)
        _progress(PipelineStep.PARSING, 1.0, f"{len(en_entries)} entries")

        # ── Step 2: Translate ──────────────────────────────────────────
        _progress(PipelineStep.TRANSLATING, 0.0)
        translator = Translator(config=self.config.translator)

        def _translate_progress(current, total, entry):
            _progress(PipelineStep.TRANSLATING, current / total,
                      f"{current}/{total}")

        vi_entries = translator.translate(en_entries, progress_callback=_translate_progress)
        _progress(PipelineStep.TRANSLATING, 1.0)

        # ── Step 3: Write SRT files ────────────────────────────────────
        _progress(PipelineStep.WRITING_SRT, 0.0)
        bilingual_path = str(out / f"{stem}_bilingual.srt")
        vi_srt_path = str(out / f"{stem}_vi.srt")
        write_bilingual_srt(en_entries, vi_entries, bilingual_path)
        write_vietnamese_srt(en_entries, vi_entries, vi_srt_path)
        _progress(PipelineStep.WRITING_SRT, 1.0)

        # ── Step 4: TTS ────────────────────────────────────────────────
        _progress(PipelineStep.TTS, 0.0)
        tts_dir = str(out / "tts_clips")
        tts_engine = TTSEngine(config=self.config.tts, output_dir=tts_dir)

        def _tts_progress(current, total, clip):
            _progress(PipelineStep.TTS, current / total, f"{current}/{total}")

        clips = tts_engine.generate_all(vi_entries, progress_callback=_tts_progress)
        _progress(PipelineStep.TTS, 1.0, f"{len(clips)} clips")

        # ── Step 5: Time-stretch ───────────────────────────────────────
        _progress(PipelineStep.STRETCHING, 0.0)
        stretch_dir = out / "stretched_clips"
        stretcher = TimeStretcher(config=self.config.stretch)
        stretched_clips = []

        for i, clip in enumerate(clips):
            stretch_path = str(stretch_dir / f"stretched_{clip.index:04d}.wav")
            try:
                result = stretcher.process(clip, output_path=stretch_path)
                if result.warning:
                    logger.warning("Clip %d: %s", clip.index, result.warning)
                stretched_clips.append(result)
            except Exception as exc:
                logger.warning("Stretch failed for clip %d, skipping: %s", clip.index, exc)
            _progress(PipelineStep.STRETCHING, (i + 1) / len(clips))

        # ── Step 6: Assemble audio track ──────────────────────────────
        _progress(PipelineStep.ASSEMBLING, 0.0)
        vi_audio_path = str(out / f"{stem}_vi.wav")

        # Build AudioClip list with updated file_paths from stretch results
        from src.tts_engine import AudioClip
        assembled_clips = []
        clip_map = {c.index: c for c in clips}
        for sr in stretched_clips:
            # find corresponding original clip for start_time
            orig = next((c for c in clips if str(stretch_dir / f"stretched_{c.index:04d}.wav") == sr.file_path
                         or sr.file_path.endswith(f"stretched_{c.index:04d}.wav")), None)
            if orig is None:
                continue
            assembled_clips.append(AudioClip(
                file_path=sr.file_path,
                actual_duration=orig.target_duration,
                target_duration=orig.target_duration,
                index=orig.index,
                start_time=orig.start_time,
            ))

        # total duration = last entry end_time
        total_dur = max((e.end_time for e in en_entries), default=0.0)
        assemble_audio(assembled_clips, total_duration=total_dur, output_path=vi_audio_path)
        _progress(PipelineStep.ASSEMBLING, 1.0)

        # ── Step 7: Merge video ────────────────────────────────────────
        _progress(PipelineStep.MERGING, 0.0)
        output_video = str(out / f"{stem}_dubbed.mp4")
        merger = AudioMerger(config=self.config.merger)
        merger.merge_video(
            video_path=video_path,
            vi_audio_path=vi_audio_path,
            output_path=output_video,
        )
        _progress(PipelineStep.MERGING, 1.0)
        _progress(PipelineStep.DONE, 1.0, output_video)

        return {
            "bilingual_srt": bilingual_path,
            "vi_srt": vi_srt_path,
            "vi_audio": vi_audio_path,
            "video": output_video,
        }


def load_pipeline_from_config(
    output_dir: str,
    config_path: str = "config/config.yaml",
) -> Pipeline:
    from src.config_loader import load_config

    cfg = load_config(config_path)
    pipeline_config = PipelineConfig(
        output_dir=output_dir,
        translator=TranslatorConfig(
            base_url=cfg.get("ollama.base_url", default="http://localhost:11434"),
            model=cfg.get("ollama.model", default="qwen3:8b"),
            timeout=cfg.get("ollama.timeout", default=60),
            max_retries=cfg.get("translator.max_retries", default=3),
            retry_delay=cfg.get("translator.retry_delay", default=1.0),
            batch_delay=cfg.get("translator.batch_delay", default=0.1),
        ),
        tts=TTSConfig(
            model_path=cfg.get(
                "tts.model_path",
                default="piper_models/vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium.onnx",
            ),
            speed=cfg.get("tts.speed", default=1.0),
        ),
        stretch=StretchConfig(
            max_speed_ratio=cfg.get("time_stretch.max_speed_ratio", default=1.6),
            min_speed_ratio=cfg.get("time_stretch.min_speed_ratio", default=0.75),
        ),
        merger=MergerConfig(
            original_volume=cfg.get("audio.original_volume", default=0.15),
            vi_volume=cfg.get("audio.vi_volume", default=1.0),
        ),
    )
    return Pipeline(config=pipeline_config)
