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
    pack: str = "Custom"  # term pack: AI/ML, Programming, Math, Custom


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


@dataclass
class FrameInfo:
    """One scene-change frame extracted from a video."""

    frame_index: int    # 1-based, matches frame filename (frame0001.jpg)
    timestamp: float    # seconds from video start
    frame_path: str     # absolute/relative path to extracted image


@dataclass
class PageContent:
    """One page of PDF notes: a frame image paired with its subtitle entries."""

    frame: FrameInfo
    entries: list       # list[SubtitleEntry | BilingualEntry]
    page_number: int = 0


@dataclass
class SearchResult:
    """One FTS hit returned from TranscriptDB.search()."""

    transcript_id: int
    title: str
    platform: str
    date_added: str     # ISO 8601 date string "YYYY-MM-DD"
    topic: str | None
    entry_id: int
    entry_index: int
    start_ms: int       # subtitle start in milliseconds
    end_ms: int
    text_en: str
    text_vi: str
    snippet: str        # short excerpt with matched terms highlighted
