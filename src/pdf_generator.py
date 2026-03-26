"""Generate PDF lecture notes from scene frames and subtitle entries.

Each page contains:
  1. A frame image captured at a scene change (top 60 % of usable height)
  2. The scene timestamp
  3. English subtitle lines (small, gray)
  4. Vietnamese subtitle lines (slightly larger, white)

Usage::

    from src.config_loader import load_config
    from src.pdf_generator import PDFGenerator

    cfg = load_config("config/config.yaml")
    gen = PDFGenerator(cfg)
    output = gen.generate(pages, "output/pdf/lecture.pdf")
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

from fpdf import FPDF

from src.config_loader import Config
from src.models import BilingualEntry, PageContent, SubtitleEntry

logger = logging.getLogger(__name__)

AnyEntry = Union[SubtitleEntry, BilingualEntry]

# macOS system fonts with broad Unicode / Vietnamese coverage, in priority order
_CANDIDATE_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

_PAGE_W = 210.0   # A4 width  in mm
_PAGE_H = 297.0   # A4 height in mm
_MARGIN = 15.0    # page margin in mm
_USABLE_W = _PAGE_W - 2 * _MARGIN
_USABLE_H = _PAGE_H - 2 * _MARGIN


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS string."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _resolve_font(config_path: str) -> str | None:
    """Return a path to a usable Unicode TTF font, or None for core Helvetica."""
    if config_path and Path(config_path).exists():
        return config_path
    for candidate in _CANDIDATE_FONTS:
        if Path(candidate).exists():
            return candidate
    logger.warning(
        "No Unicode font found. Vietnamese characters may not render correctly. "
        "Set pdf.font_path in config.yaml to a Unicode TTF."
    )
    return None


def _entry_text(entry: AnyEntry) -> tuple[str, str]:
    """Return (text_en, text_vi) from either entry type."""
    if isinstance(entry, BilingualEntry):
        return entry.text_en, entry.text_vi
    return entry.text, ""


class PDFGenerator:
    """Generate A4 PDF lecture notes from :class:`~src.models.PageContent` data.

    Configuration keys (under ``pdf.*`` in config.yaml):

    * ``font_path`` – path to a Unicode TTF. Empty = auto-detect macOS Arial.
    * ``image_height_ratio`` – fraction of usable page height for the frame image.
    * ``en_font_size`` – English text size in pt.
    * ``vi_font_size`` – Vietnamese text size in pt.
    """

    def __init__(self, config: Config) -> None:
        self.font_path: str = config.get("pdf.font_path", "") or ""
        self.image_height_ratio: float = float(
            config.get("pdf.image_height_ratio", 0.60)
        )
        self.en_font_size: int = int(config.get("pdf.en_font_size", 9))
        self.vi_font_size: int = int(config.get("pdf.vi_font_size", 12))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        pages: list[PageContent],
        output_path: str | Path,
    ) -> Path:
        """Render *pages* to a PDF file at *output_path*.

        Args:
            pages: List of :class:`~src.models.PageContent`, one per scene frame.
            output_path: Destination PDF path.  Parent directory is created if needed.

        Returns:
            The resolved :class:`pathlib.Path` of the written PDF.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=_MARGIN)
        pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)

        font_name = self._register_font(pdf)
        img_h = _USABLE_H * self.image_height_ratio  # mm

        for page in pages:
            pdf.add_page()
            self._render_page(pdf, page, font_name, img_h)

        pdf.output(str(output_path))
        logger.info("PDF written to %s (%d page(s))", output_path, len(pages))
        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register_font(self, pdf: FPDF) -> str:
        """Register the best available font and return its name for set_font()."""
        resolved = _resolve_font(self.font_path)
        if resolved:
            try:
                pdf.add_font("VietFont", fname=resolved)
                return "VietFont"
            except Exception as exc:
                logger.warning("Failed to load font %s: %s — falling back to helvetica", resolved, exc)
        return "helvetica"

    def _render_page(
        self,
        pdf: FPDF,
        page: PageContent,
        font_name: str,
        img_h: float,
    ) -> None:
        """Render a single page: image + timestamp + subtitle lines."""
        frame = page.frame

        # ── Frame image ───────────────────────────────────────────────
        if Path(frame.frame_path).exists():
            pdf.image(
                frame.frame_path,
                x=_MARGIN,
                y=_MARGIN,
                w=_USABLE_W,
                h=img_h,
            )
        else:
            logger.debug("Frame image not found, skipping: %s", frame.frame_path)

        # Move cursor below image
        pdf.set_y(_MARGIN + img_h + 3)

        # ── Timestamp ─────────────────────────────────────────────────
        pdf.set_font(font_name, size=9)
        pdf.set_text_color(120, 120, 120)  # gray
        pdf.multi_cell(
            _USABLE_W, 5,
            f"[{_format_timestamp(frame.timestamp)}]",
            align="L",
        )

        # ── Subtitle entries ──────────────────────────────────────────
        for entry in page.entries:
            text_en, text_vi = _entry_text(entry)
            if text_en:
                pdf.set_font(font_name, size=self.en_font_size)
                pdf.set_text_color(140, 140, 140)  # light gray for EN
                pdf.multi_cell(_USABLE_W, 4, text_en, align="L")
            if text_vi:
                pdf.set_font(font_name, size=self.vi_font_size)
                pdf.set_text_color(220, 220, 220)  # near-white for VI
                pdf.multi_cell(_USABLE_W, 5, text_vi, align="L")
            pdf.ln(2)  # small gap between entries
