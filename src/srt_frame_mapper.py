"""Assign subtitle entries to the nearest preceding scene-change frame.

This produces :class:`~src.models.PageContent` objects that drive the PDF
generator — one page per scene frame, each page carrying the subtitle lines
that belong to that scene.
"""
from __future__ import annotations

import logging
from typing import Union

from src.models import BilingualEntry, FrameInfo, PageContent, SubtitleEntry

logger = logging.getLogger(__name__)

AnyEntry = Union[SubtitleEntry, BilingualEntry]


def _entry_start(entry: AnyEntry) -> float:
    """Return the start time of an entry in seconds."""
    if isinstance(entry, BilingualEntry):
        # BilingualEntry stores timestamps as "HH:MM:SS,mmm" strings
        ts = entry.start.replace(",", ".")
        parts = ts.split(":")
        h, m, rest = int(parts[0]), int(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + rest
    return entry.start_time


class SRTFrameMapper:
    """Map subtitle entries to scene-change frames.

    Assignment strategy: each entry is assigned to the latest frame whose
    timestamp is ≤ the entry's start time.  Entries that precede the very
    first frame are assigned to that first frame.

    This mirrors how a viewer would see the video: the current scene is the
    most recent cut, so captions belong to that cut's frame.
    """

    def map(
        self,
        frames: list[FrameInfo],
        entries: list[AnyEntry],
    ) -> list[PageContent]:
        """Assign *entries* to *frames* and return one :class:`PageContent` per frame.

        Args:
            frames: Scene-change frames (any order; will be sorted internally).
            entries: Subtitle entries — either :class:`SubtitleEntry` or
                     :class:`BilingualEntry`.

        Returns:
            List of :class:`PageContent` sorted by frame timestamp.
            If *frames* is empty, returns ``[]``.
            Frames with no matching entries still appear (``entries=[]``).
        """
        if not frames:
            logger.warning("No frames provided to SRTFrameMapper.map()")
            return []

        sorted_frames = sorted(frames, key=lambda f: f.timestamp)

        pages: list[PageContent] = [
            PageContent(frame=f, entries=[], page_number=i + 1)
            for i, f in enumerate(sorted_frames)
        ]

        for entry in entries:
            t = _entry_start(entry)
            page_idx = self._frame_for_time(sorted_frames, t)
            pages[page_idx].entries.append(entry)

        logger.debug(
            "Mapped %d subtitle entries across %d pages",
            len(entries),
            len(pages),
        )
        return pages

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _frame_for_time(sorted_frames: list[FrameInfo], t: float) -> int:
        """Return the index (into sorted_frames) of the latest frame at or before *t*.

        Uses binary search for O(log n) lookup.  Returns 0 if *t* is before
        the first frame so those entries land on the first page.
        """
        lo, hi, best = 0, len(sorted_frames) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if sorted_frames[mid].timestamp <= t:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return best
