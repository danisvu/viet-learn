"""URL-type detection helpers shared by YouTube view and tests."""
from __future__ import annotations


def detect_url_type(url: str) -> tuple[str, bool]:
    """Classify a YouTube URL without making any network request.

    Args:
        url: Raw string from the URL input field.

    Returns:
        ``(badge_text, is_playlist)`` where *badge_text* is one of
        ``"Video"``, ``"Playlist"``, or ``""`` (unrecognised / empty).
    """
    url = url.strip()
    if not url:
        return "", False
    # A URL containing list= is a playlist (even if it also has v=)
    if "list=" in url or "youtube.com/playlist" in url:
        return "Playlist", True
    if "youtu.be/" in url or "v=" in url or "youtube.com/watch" in url:
        return "Video", False
    return "", False
