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
