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
