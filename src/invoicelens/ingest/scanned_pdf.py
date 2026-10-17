"""Scanned PDF loader: render pages to PNG at DPI, OCR with Tesseract via pytesseract."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from ..models import DocumentText, Page
from ..settings import get_settings


def _tesseract_cmd() -> str:
    return get_settings().tesseract_cmd


def load(path: str | Path, doc_id: str | None = None) -> DocumentText:
    p = Path(path)
    doc_id = doc_id or p.stem
    cfg = get_settings()
    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    dpi = cfg.ocr_dpi
    doc = fitz.open(p)
    pages: list[Page] = []
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(img)
            # mean word-level confidence (only words with conf > 0)
            confs = [c for c in data.get("conf", []) if isinstance(c, (int, float)) and c > 0]
            mean_conf = sum(confs) / len(confs) if confs else None
            pages.append(Page(ref=f"p{i}", text=text.strip(), ocr_confidence=mean_conf))
    finally:
        doc.close()
    return DocumentText(doc_id=doc_id, doc_type="scanned_pdf", pages=pages, source_path=str(p.resolve()))


def marked_text(doc: DocumentText) -> str:
    out = []
    for pg in doc.pages:
        out.append(f"[{pg.ref}]")
        out.append(pg.text)
    return "\n".join(out)
