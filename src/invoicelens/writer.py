"""Writer: emit out/<doc_id>.json and out/<doc_id>.csv (one row per field)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .confidence import iter_fields
from .models import DocumentText, InvoiceDoc


def source_link(doc: InvoiceDoc, doc_text: DocumentText, page: str | None) -> str:
    if not page:
        return ""
    base = doc_text.source_path
    if doc_text.doc_type == "email":
        return f"{base}#body"
    if doc_text.doc_type == "spreadsheet":
        return f"{base}#{page}"
    # pdf: #page=N where N is the numeric part of the ref
    n = "".join(ch for ch in page if ch.isdigit()) or "1"
    return f"file:///{Path(base).resolve().as_posix()}#page={n}"


def _jsonable(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "__str__") and type(v).__name__ == "Decimal":
        return float(v)
    return v


def doc_to_dict(doc: InvoiceDoc) -> dict:
    def field(f):
        return {
            "value": _jsonable(f.value),
            "source": f.source.model_dump() if f.source else None,
            "llm_confidence": f.llm_confidence,
            "confidence": f.confidence,
            "status": f.status,
        }

    return {
        "doc_id": doc.doc_id,
        "doc_kind": field(doc.doc_kind),
        "supplier_name": field(doc.supplier_name),
        "supplier_tax_id": field(doc.supplier_tax_id),
        "document_number": field(doc.document_number),
        "issue_date": field(doc.issue_date),
        "due_date": field(doc.due_date),
        "currency": field(doc.currency),
        "line_items": [
            {
                "description": field(li.description),
                "quantity": field(li.quantity),
                "unit_price": field(li.unit_price),
                "amount": field(li.amount),
            }
            for li in doc.line_items
        ],
        "subtotal": field(doc.subtotal),
        "tax_total": field(doc.tax_total),
        "total": field(doc.total),
    }


def write(doc: InvoiceDoc, doc_text: DocumentText, out_dir: str | Path) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jpath = out / f"{doc.doc_id}.json"
    cpath = out / f"{doc.doc_id}.csv"

    jpath.write_text(json.dumps(doc_to_dict(doc), indent=2), encoding="utf-8")

    with open(cpath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["field_path", "value", "source_page", "source_link", "llm_confidence", "confidence", "status"])
        for path, fld in iter_fields(doc):
            page = fld.source.page if fld.source else ""
            w.writerow(
                [
                    path,
                    _jsonable(fld.value),
                    page,
                    source_link(doc, doc_text, page),
                    fld.llm_confidence,
                    round(fld.confidence, 3),
                    fld.status,
                ]
            )
    return jpath, cpath
