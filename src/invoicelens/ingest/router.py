"""Router: detect document type from a path.

Rules (IDEATION 4.2):
  .eml            -> email
  .xlsx/.csv      -> spreadsheet
  .pdf            -> text_pdf if avg extractable chars/page >= threshold else scanned_pdf
"""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

from ..settings import get_settings

EMAIL_EXT = {".eml"}
SHEET_EXT = {".xlsx", ".csv"}
PDF_EXT = {".pdf"}


def detect(path: str | Path) -> str:
    """Return one of text_pdf | scanned_pdf | spreadsheet | email."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in EMAIL_EXT:
        return "email"
    if ext in SHEET_EXT:
        return "spreadsheet"
    if ext in PDF_EXT:
        return _pdf_type(p)
    raise ValueError(f"unsupported file type: {ext!r} ({p})")


def _pdf_type(path: Path, min_chars: int | None = None) -> str:
    if min_chars is None:
        min_chars = get_settings().ocr_min_chars_per_page
    doc = fitz.open(path)
    try:
        n = doc.page_count or 1
        total = 0
        for page in doc:
            total += len(page.get_text().strip())
        avg = total / n
        return "text_pdf" if avg >= min_chars else "scanned_pdf"
    finally:
        doc.close()
