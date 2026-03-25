from dataclasses import dataclass
from enum import Enum


@dataclass
class SubtitleEntry:
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    text: str


class GlossaryMode(str, Enum):
    KEEP_ENGLISH = "keep_english"
    TRANSLATE_ANNOTATE = "translate_annotate"
    REPLACE = "replace"


@dataclass
class GlossaryTerm:
    english: str       # term to match (case-insensitive)
    vietnamese: str    # Vietnamese equivalent (empty for KEEP_ENGLISH)
    mode: GlossaryMode


@dataclass
class DownloadResult:
    video_id: str
    title: str
    video_path: str
    subtitle_path: str | None   # None if no subtitle found
    subtitle_fallback: bool     # True = auto-generated captions were used
    srt_not_found: bool         # True = no subtitle of any kind found
    webpage_url: str


@dataclass
class BilingualEntry:
    """One subtitle entry with both source and translated text."""

    index: int
    start: str          # "HH:MM:SS,mmm" timestamp string
    end: str
    text_en: str
    text_vi: str
    audio_path: str | None = None  # path to per-entry TTS audio clip
    edited: bool = False
