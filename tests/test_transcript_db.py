"""Tests for src.transcript_db — SQLite FTS5 search."""
from __future__ import annotations

import pytest

from src.models import BilingualEntry, SearchResult, SubtitleEntry
from src.transcript_db import TranscriptDB, _ms_to_timestamp, _sanitize_fts_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """In-memory-ish DB in a temp directory."""
    with TranscriptDB(tmp_path / "test.db") as database:
        yield database


def _bilingual(idx: int, text_en: str, text_vi: str = "") -> BilingualEntry:
    h = idx // 60
    m = idx % 60
    ts = f"{h:02d}:{m:02d}:00,000"
    return BilingualEntry(
        index=idx, start=ts, end=ts, text_en=text_en, text_vi=text_vi or text_en
    )


def _subtitle(idx: int, text: str) -> SubtitleEntry:
    return SubtitleEntry(index=idx, start_time=float(idx * 5), end_time=float(idx * 5 + 3), text=text)


# ---------------------------------------------------------------------------
# Schema / lifecycle
# ---------------------------------------------------------------------------

def test_db_creates_tables(db):
    tables = {
        row[0]
        for row in db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "transcripts" in tables
    assert "subtitle_entries" in tables


def test_context_manager(tmp_path):
    with TranscriptDB(tmp_path / "cm.db") as db:
        tid = db.add_transcript("test", "youtube", "2024-01-01")
    # After exit, connection should be closed (further use raises)
    with pytest.raises(Exception):
        db._conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# add_transcript / list_transcripts
# ---------------------------------------------------------------------------

def test_add_transcript_returns_id(db):
    tid = db.add_transcript("Lecture 1", "youtube", "2024-03-01", url="https://yt.be/abc")
    assert isinstance(tid, int)
    assert tid > 0


def test_list_transcripts_empty(db):
    assert db.list_transcripts() == []


def test_list_transcripts_all(db):
    db.add_transcript("A", "youtube", "2024-01-01")
    db.add_transcript("B", "dlai", "2024-02-01")
    rows = db.list_transcripts()
    assert len(rows) == 2
    titles = {r["title"] for r in rows}
    assert titles == {"A", "B"}


def test_list_transcripts_by_platform(db):
    db.add_transcript("YT vid", "youtube", "2024-01-01")
    db.add_transcript("DLAI course", "dlai", "2024-01-01")
    yt = db.list_transcripts(platform="youtube")
    assert len(yt) == 1
    assert yt[0]["title"] == "YT vid"


# ---------------------------------------------------------------------------
# add_entries
# ---------------------------------------------------------------------------

def test_add_bilingual_entries(db):
    tid = db.add_transcript("T", "youtube", "2024-01-01")
    entries = [_bilingual(i, f"Hello world {i}", f"Xin chào {i}") for i in range(3)]
    db.add_entries(tid, entries)
    rows = db._conn.execute(
        "SELECT COUNT(*) FROM subtitle_entries WHERE transcript_id = ?", (tid,)
    ).fetchone()
    assert rows[0] == 3


def test_add_subtitle_entries(db):
    tid = db.add_transcript("T2", "udemy", "2024-01-01")
    entries = [_subtitle(i, f"Neural networks {i}") for i in range(5)]
    db.add_entries(tid, entries)
    count = db._conn.execute(
        "SELECT COUNT(*) FROM subtitle_entries WHERE transcript_id = ?", (tid,)
    ).fetchone()[0]
    assert count == 5


# ---------------------------------------------------------------------------
# delete_transcript (cascade)
# ---------------------------------------------------------------------------

def test_delete_cascades(db):
    tid = db.add_transcript("Del", "youtube", "2024-01-01")
    db.add_entries(tid, [_bilingual(0, "machine learning")])
    db.delete_transcript(tid)
    count = db._conn.execute(
        "SELECT COUNT(*) FROM subtitle_entries WHERE transcript_id = ?", (tid,)
    ).fetchone()[0]
    assert count == 0


# ---------------------------------------------------------------------------
# search — basic FTS
# ---------------------------------------------------------------------------

def _seed(db: TranscriptDB) -> tuple[int, int]:
    """Seed two transcripts and return their IDs."""
    t1 = db.add_transcript("ML Basics", "youtube", "2024-01-15", topic="machine learning")
    db.add_entries(t1, [
        _bilingual(0, "Gradient descent is an optimization algorithm", "Gradient descent là thuật toán tối ưu"),
        _bilingual(1, "Backpropagation computes gradients", "Lan truyền ngược tính gradient"),
        _bilingual(2, "Neural networks learn representations", "Mạng nơ-ron học biểu diễn"),
    ])
    t2 = db.add_transcript("NLP Course", "dlai", "2024-02-20", topic="NLP")
    db.add_entries(t2, [
        _bilingual(0, "Transformer architecture uses attention", "Transformer dùng attention"),
        _bilingual(1, "BERT is a large language model", "BERT là mô hình ngôn ngữ lớn"),
    ])
    return t1, t2


def test_search_returns_results(db):
    _seed(db)
    results = db.search("gradient")
    assert len(results) >= 1
    assert all(isinstance(r, SearchResult) for r in results)


def test_search_matches_english(db):
    _seed(db)
    results = db.search("backpropagation")
    assert len(results) == 1
    assert "backpropagation" in results[0].text_en.lower()


def test_search_matches_vietnamese(db):
    _seed(db)
    results = db.search("attention")
    assert len(results) >= 1
    texts = [r.text_en + r.text_vi for r in results]
    assert any("attention" in t.lower() for t in texts)


def test_search_empty_query_returns_empty(db):
    _seed(db)
    assert db.search("") == []
    assert db.search("   ") == []


def test_search_no_match(db):
    _seed(db)
    results = db.search("xylophone123")
    assert results == []


def test_search_result_fields(db):
    t1, _ = _seed(db)
    results = db.search("gradient descent")
    r = results[0]
    assert r.transcript_id == t1
    assert r.title == "ML Basics"
    assert r.platform == "youtube"
    assert r.date_added == "2024-01-15"
    assert r.topic == "machine learning"
    assert isinstance(r.entry_index, int)
    assert r.start_ms >= 0
    assert r.end_ms >= 0
    assert isinstance(r.snippet, str)


# ---------------------------------------------------------------------------
# search — filters
# ---------------------------------------------------------------------------

def test_search_filter_platform(db):
    _seed(db)
    results = db.search("model", platform="dlai")
    assert all(r.platform == "dlai" for r in results)


def test_search_filter_date_from(db):
    _seed(db)
    results = db.search("gradient", date_from="2024-02-01")
    # ML Basics is 2024-01-15 → should be excluded
    assert all(r.date_added >= "2024-02-01" for r in results)


def test_search_filter_date_to(db):
    _seed(db)
    results = db.search("attention", date_to="2024-01-31")
    assert all(r.date_added <= "2024-01-31" for r in results)


def test_search_filter_topic(db):
    _seed(db)
    results = db.search("model", topic="NLP")
    assert all(r.topic is not None and "NLP" in r.topic for r in results)


def test_search_limit(db):
    tid = db.add_transcript("Big", "youtube", "2024-01-01")
    entries = [_bilingual(i, f"deep learning lecture {i}") for i in range(50)]
    db.add_entries(tid, entries)
    results = db.search("deep learning", limit=10)
    assert len(results) <= 10


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def test_sanitize_fts_query_basic():
    assert _sanitize_fts_query("neural network") == '"neural"* "network"*'


def test_sanitize_fts_query_strips_special():
    # Quotes stripped; AND is treated as a regular token, not an FTS operator
    result = _sanitize_fts_query('"neural" AND network')
    assert result  # not empty — sanitizer keeps the meaningful tokens
    assert result.startswith('"')  # output is properly quoted for FTS5


def test_sanitize_fts_query_empty():
    assert _sanitize_fts_query("") == ""
    assert _sanitize_fts_query("   ") == ""


def test_ms_to_timestamp():
    assert _ms_to_timestamp(0) == "00:00"
    assert _ms_to_timestamp(61_000) == "01:01"
    assert _ms_to_timestamp(3_661_000) == "01:01:01"
