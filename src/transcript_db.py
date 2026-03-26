"""SQLite database with FTS5 full-text search for VietLearn transcripts.

Schema
------
transcripts          – one row per processed video
subtitle_entries     – one row per subtitle segment
subtitle_fts         – FTS5 virtual table (mirrors subtitle_entries)

Triggers keep subtitle_fts in sync with subtitle_entries automatically.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from src.models import BilingualEntry, SearchResult, SubtitleEntry

logger = logging.getLogger(__name__)

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS transcripts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    platform    TEXT    NOT NULL DEFAULT 'other',
    url         TEXT,
    date_added  TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    topic       TEXT,
    srt_path    TEXT,
    video_path  TEXT
);

CREATE TABLE IF NOT EXISTS subtitle_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id   INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    entry_index     INTEGER NOT NULL,
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL,
    text_en         TEXT    NOT NULL DEFAULT '',
    text_vi         TEXT    NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS subtitle_fts USING fts5(
    text_en,
    text_vi,
    content='subtitle_entries',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS fts_after_insert
    AFTER INSERT ON subtitle_entries BEGIN
        INSERT INTO subtitle_fts(rowid, text_en, text_vi)
        VALUES (new.id, new.text_en, new.text_vi);
    END;

CREATE TRIGGER IF NOT EXISTS fts_after_delete
    AFTER DELETE ON subtitle_entries BEGIN
        INSERT INTO subtitle_fts(subtitle_fts, rowid, text_en, text_vi)
        VALUES ('delete', old.id, old.text_en, old.text_vi);
    END;

CREATE TRIGGER IF NOT EXISTS fts_after_update
    AFTER UPDATE ON subtitle_entries BEGIN
        INSERT INTO subtitle_fts(subtitle_fts, rowid, text_en, text_vi)
        VALUES ('delete', old.id, old.text_en, old.text_vi);
        INSERT INTO subtitle_fts(rowid, text_en, text_vi)
        VALUES (new.id, new.text_en, new.text_vi);
    END;

CREATE INDEX IF NOT EXISTS idx_entries_transcript
    ON subtitle_entries(transcript_id);
CREATE INDEX IF NOT EXISTS idx_transcripts_platform
    ON transcripts(platform);
CREATE INDEX IF NOT EXISTS idx_transcripts_date
    ON transcripts(date_added);
"""


def _ms_to_timestamp(ms: int) -> str:
    """Format milliseconds as MM:SS or HH:MM:SS."""
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def _ms_from_subtitle(entry: SubtitleEntry | BilingualEntry) -> tuple[int, int]:
    """Return (start_ms, end_ms) from either entry type."""
    if isinstance(entry, BilingualEntry):
        return _timestamp_to_ms(entry.start), _timestamp_to_ms(entry.end)
    # SubtitleEntry stores floats in seconds
    return int(entry.start_time * 1000), int(entry.end_time * 1000)


def _timestamp_to_ms(ts: str) -> int:
    """Convert 'HH:MM:SS,mmm' or 'HH:MM:SS.mmm' to milliseconds."""
    ts = ts.replace(",", ".")
    parts = ts.split(":")
    h, m, rest = int(parts[0]), int(parts[1]), float(parts[2])
    return int((h * 3600 + m * 60 + rest) * 1000)


def _sanitize_fts_query(raw: str) -> str:
    """Return a safe FTS5 MATCH expression for arbitrary user input."""
    # Strip FTS special operators to avoid syntax errors
    cleaned = re.sub(r'[":^*()]', " ", raw).strip()
    if not cleaned:
        return ""
    # Wrap each token so FTS5 treats them as prefix searches
    tokens = cleaned.split()
    return " ".join(f'"{t}"*' for t in tokens)


class TranscriptDB:
    """Persistent store for transcripts with FTS5 search capability."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def add_transcript(
        self,
        title: str,
        platform: str,
        date_added: str,
        *,
        url: str | None = None,
        topic: str | None = None,
        srt_path: str | None = None,
        video_path: str | None = None,
    ) -> int:
        """Insert a transcript record and return its new id."""
        cur = self._conn.execute(
            """INSERT INTO transcripts(title, platform, url, date_added, topic,
                                       srt_path, video_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, platform, url, date_added, topic, srt_path, video_path),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def add_entries(
        self,
        transcript_id: int,
        entries: list[SubtitleEntry | BilingualEntry],
    ) -> None:
        """Bulk-insert subtitle entries for *transcript_id*."""
        rows: list[tuple[Any, ...]] = []
        for e in entries:
            start_ms, end_ms = _ms_from_subtitle(e)
            if isinstance(e, BilingualEntry):
                text_en, text_vi = e.text_en, e.text_vi
                idx = e.index
            else:
                text_en, text_vi = e.text, ""
                idx = e.index
            rows.append((transcript_id, idx, start_ms, end_ms, text_en, text_vi))

        self._conn.executemany(
            """INSERT INTO subtitle_entries
               (transcript_id, entry_index, start_ms, end_ms, text_en, text_vi)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        self._conn.commit()
        logger.debug("Inserted %d subtitle entries for transcript %d", len(rows), transcript_id)

    def delete_transcript(self, transcript_id: int) -> None:
        """Remove a transcript and all its entries (cascades to FTS)."""
        self._conn.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        platform: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        topic: str | None = None,
        limit: int = 500,
    ) -> list[SearchResult]:
        """Full-text search across subtitle_entries.

        Returns up to *limit* results ordered by FTS relevance rank.
        Empty *query* returns an empty list.
        """
        fts_query = _sanitize_fts_query(query)
        if not fts_query:
            return []

        filters: list[str] = []
        params: list[Any] = [fts_query]

        if platform:
            filters.append("t.platform = ?")
            params.append(platform)
        if date_from:
            filters.append("t.date_added >= ?")
            params.append(date_from)
        if date_to:
            filters.append("t.date_added <= ?")
            params.append(date_to)
        if topic:
            filters.append("t.topic LIKE ?")
            params.append(f"%{topic}%")

        where_extra = ("AND " + " AND ".join(filters)) if filters else ""
        params.append(limit)

        sql = f"""
            SELECT
                t.id            AS transcript_id,
                t.title,
                t.platform,
                t.date_added,
                t.topic,
                se.id           AS entry_id,
                se.entry_index,
                se.start_ms,
                se.end_ms,
                se.text_en,
                se.text_vi,
                snippet(subtitle_fts, 0, '**', '**', ' … ', 20) AS snip_en,
                snippet(subtitle_fts, 1, '**', '**', ' … ', 20) AS snip_vi
            FROM subtitle_fts
            JOIN subtitle_entries se ON subtitle_fts.rowid = se.id
            JOIN transcripts t ON se.transcript_id = t.id
            WHERE subtitle_fts MATCH ?
            {where_extra}
            ORDER BY rank
            LIMIT ?
        """
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS query failed (%s), query=%r", exc, query)
            return []

        results: list[SearchResult] = []
        for r in rows:
            snippet = r["snip_en"] if r["snip_en"] else r["snip_vi"]
            results.append(
                SearchResult(
                    transcript_id=r["transcript_id"],
                    title=r["title"],
                    platform=r["platform"],
                    date_added=r["date_added"],
                    topic=r["topic"],
                    entry_id=r["entry_id"],
                    entry_index=r["entry_index"],
                    start_ms=r["start_ms"],
                    end_ms=r["end_ms"],
                    text_en=r["text_en"],
                    text_vi=r["text_vi"],
                    snippet=snippet or "",
                )
            )
        return results

    def list_transcripts(
        self, *, platform: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all transcripts, optionally filtered by platform."""
        if platform:
            rows = self._conn.execute(
                "SELECT * FROM transcripts WHERE platform = ? ORDER BY date_added DESC",
                (platform,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM transcripts ORDER BY date_added DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self) -> "TranscriptDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
