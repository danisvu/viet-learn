"""Tests for src.pdf_generator — PDF lecture notes generation."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.config_loader import Config
from src.models import BilingualEntry, FrameInfo, PageContent, SubtitleEntry
from src.pdf_generator import PDFGenerator, _format_timestamp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(**overrides) -> Config:
    data = {
        "pdf": {
            "font_path": "",
            "output_dir": "output/pdf",
            "image_height_ratio": 0.60,
            "en_font_size": 9,
            "vi_font_size": 12,
            **overrides,
        }
    }
    return Config(data)


def _frame(index: int = 1, ts: float = 0.0, path: str = "frame0001.jpg") -> FrameInfo:
    return FrameInfo(frame_index=index, timestamp=ts, frame_path=path)


def _sub(text_en: str = "Hello world", text_vi: str = "Xin chào thế giới") -> BilingualEntry:
    return BilingualEntry(
        index=0, start="00:00:01,000", end="00:00:03,000",
        text_en=text_en, text_vi=text_vi,
    )


def _page(frame: FrameInfo | None = None, entries=None, page_number: int = 1) -> PageContent:
    return PageContent(
        frame=frame or _frame(),
        entries=entries or [],
        page_number=page_number,
    )


# ---------------------------------------------------------------------------
# _format_timestamp
# ---------------------------------------------------------------------------

def test_format_timestamp_zero():
    assert _format_timestamp(0.0) == "00:00:00"


def test_format_timestamp_minutes():
    assert _format_timestamp(125.0) == "00:02:05"


def test_format_timestamp_hours():
    assert _format_timestamp(3723.5) == "01:02:03"


# ---------------------------------------------------------------------------
# PDFGenerator construction
# ---------------------------------------------------------------------------

def test_reads_en_font_size():
    gen = PDFGenerator(_cfg(en_font_size=8))
    assert gen.en_font_size == 8


def test_reads_vi_font_size():
    gen = PDFGenerator(_cfg(vi_font_size=14))
    assert gen.vi_font_size == 14


def test_reads_image_height_ratio():
    gen = PDFGenerator(_cfg(image_height_ratio=0.5))
    assert gen.image_height_ratio == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# generate() — output file
# ---------------------------------------------------------------------------

@patch("src.pdf_generator.FPDF")
def test_generate_creates_output_file(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    gen = PDFGenerator(_cfg())
    out = tmp_path / "notes.pdf"
    result = gen.generate([_page()], out)

    mock_pdf.output.assert_called_once_with(str(out))
    assert result == out


@patch("src.pdf_generator.FPDF")
def test_generate_adds_one_page_per_content(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    pages = [_page(page_number=i + 1) for i in range(3)]
    gen = PDFGenerator(_cfg())
    gen.generate(pages, tmp_path / "out.pdf")

    assert mock_pdf.add_page.call_count == 3


@patch("src.pdf_generator.FPDF")
def test_generate_empty_pages_still_outputs_file(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    gen = PDFGenerator(_cfg())
    gen.generate([], tmp_path / "empty.pdf")
    mock_pdf.output.assert_called_once()


@patch("src.pdf_generator.FPDF")
def test_generate_returns_path_object(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    gen = PDFGenerator(_cfg())
    result = gen.generate([], tmp_path / "out.pdf")
    assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# generate() — image embedding
# ---------------------------------------------------------------------------

@patch("src.pdf_generator.FPDF")
def test_generate_embeds_image_when_frame_exists(mock_fpdf_cls, tmp_path):
    # Create a fake image file
    fake_img = tmp_path / "frame0001.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff")  # JPEG magic bytes

    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    page = _page(frame=_frame(path=str(fake_img)))
    gen = PDFGenerator(_cfg())
    gen.generate([page], tmp_path / "out.pdf")

    mock_pdf.image.assert_called_once()
    assert str(fake_img) in mock_pdf.image.call_args[0]


@patch("src.pdf_generator.FPDF")
def test_generate_skips_image_when_frame_missing(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    page = _page(frame=_frame(path="/nonexistent/frame.jpg"))
    gen = PDFGenerator(_cfg())
    gen.generate([page], tmp_path / "out.pdf")

    mock_pdf.image.assert_not_called()


# ---------------------------------------------------------------------------
# generate() — text content
# ---------------------------------------------------------------------------

@patch("src.pdf_generator.FPDF")
def test_generate_writes_entry_text(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    entry = _sub("Gradient descent", "Gradient descent là")
    page = _page(entries=[entry])
    gen = PDFGenerator(_cfg())
    gen.generate([page], tmp_path / "out.pdf")

    # multi_cell should be called for text output
    assert mock_pdf.multi_cell.call_count >= 1


@patch("src.pdf_generator.FPDF")
def test_generate_writes_timestamp_text(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    page = _page(frame=_frame(ts=125.0))
    gen = PDFGenerator(_cfg())
    gen.generate([page], tmp_path / "out.pdf")

    # The timestamp "00:02:05" should appear somewhere in multi_cell calls
    all_text_args = [
        str(c.args) + str(c.kwargs)
        for c in mock_pdf.multi_cell.call_args_list
    ]
    timestamp_written = any("00:02:05" in t for t in all_text_args)
    assert timestamp_written


# ---------------------------------------------------------------------------
# generate() — creates parent directory
# ---------------------------------------------------------------------------

@patch("src.pdf_generator.FPDF")
def test_generate_creates_output_parent_dir(mock_fpdf_cls, tmp_path):
    mock_pdf = MagicMock()
    mock_fpdf_cls.return_value = mock_pdf

    out = tmp_path / "nested" / "deep" / "notes.pdf"
    gen = PDFGenerator(_cfg())
    gen.generate([], out)

    assert out.parent.exists()
