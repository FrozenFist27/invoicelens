"""Text PDF loader: per-page text via PyMuPDF, page refs p1..pN."""

from __future__ import annotations

from pathlib import Path

import fitz

from ..models import DocumentText, Page


def load(path: str | Path, doc_id: str | None = None) -> DocumentText:
    p = Path(path)
    doc_id = doc_id or p.stem
    doc = fitz.open(p)
    pages: list[Page] = []
    try:
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            pages.append(Page(ref=f"p{i}", text=text, ocr_confidence=None))
    finally:
        doc.close()
    return DocumentText(doc_id=doc_id, doc_type="text_pdf", pages=pages, source_path=str(p.resolve()))


def marked_text(doc: DocumentText) -> str:
    """Prefix each page's text with [pN] markers so the LLM can cite page refs."""
    out = []
    for pg in doc.pages:
        out.append(f"[{pg.ref}]")
        out.append(pg.text)
    return "\n".join(out)
