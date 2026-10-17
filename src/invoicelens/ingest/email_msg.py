"""Email loader: parse .eml with stdlib email, extract body text, route attachments.

Attachments with pdf/xlsx/csv extensions are extracted to a temp dir and can be
re-loaded by the router recursively (the pipeline handles this).
"""

from __future__ import annotations

import email
import email.policy
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..models import DocumentText, Page

ATTACH_EXTS = {".pdf", ".xlsx", ".csv"}


@dataclass
class ExtractedAttachment:
    filename: str
    saved_path: Path


def load(path: str | Path, doc_id: str | None = None, extract_attachments_to: str | None = None) -> tuple[DocumentText, list[ExtractedAttachment]]:
    """Parse an .eml file. Returns (DocumentText for the body, list of extracted attachments)."""
    p = Path(path)
    doc_id = doc_id or p.stem
    with open(p, "rb") as f:
        msg = email.message_from_binary_file(f, policy=email.policy.default)

    body_parts: list[str] = []
    attachments: list[ExtractedAttachment] = []

    out_dir = Path(extract_attachments_to) if extract_attachments_to else Path(tempfile.mkdtemp(prefix="invoicelens_eml_"))
    out_dir.mkdir(parents=True, exist_ok=True)

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        ctype = part.get_content_type()
        if filename:
            ext = Path(filename).suffix.lower()
            if ext in ATTACH_EXTS:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                safe_name = Path(filename).name
                saved = out_dir / f"{doc_id}_{safe_name}"
                saved.write_bytes(payload)
                attachments.append(ExtractedAttachment(filename=safe_name, saved_path=saved))
        elif ctype == "text/plain":
            try:
                body_parts.append(part.get_content())
            except Exception:
                raw = part.get_payload(decode=True) or b""
                body_parts.append(raw.decode("utf-8", errors="replace"))
        elif ctype == "text/html" and not body_parts:
            try:
                body_parts.append(part.get_content())
            except Exception:
                pass

    body = "\n".join(body_parts).strip()
    subject = str(msg.get("Subject", "") or "")
    sender = str(msg.get("From", "") or "")
    page = Page(ref="body", text=f"From: {sender}\nSubject: {subject}\n\n{body}", ocr_confidence=None)
    doc = DocumentText(doc_id=doc_id, doc_type="email", pages=[page], source_path=str(p.resolve()))
    return doc, attachments


def marked_text(doc: DocumentText) -> str:
    out = []
    for pg in doc.pages:
        out.append(f"[{pg.ref}]")
        out.append(pg.text)
    return "\n".join(out)
