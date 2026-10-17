"""Extractor + corrector orchestration (IDEATION 4.2 steps 3-5).

- parse_flat(): flattened tool dict -> InvoiceDoc (with llm_confidence + source)
- extract(): one extraction call
- correct(): targeted correction retry (max_retries)
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .llm.prompts import (
    CORRECTION_SYSTEM,
    CORRECTION_TOOL,
    CORRECTION_USER,
    EXTRACT_SYSTEM,
    EXTRACT_USER,
    INVOICE_TOOL,
    TOOL_NAME,
)
from .models import Field, InvoiceDoc, LineItem, SourceRef, Usage
from .validate import fields_with_issues


def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    s = str(v).strip().replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _to_field(flat: dict | None, parser=None) -> Field:
    if not isinstance(flat, dict):
        return Field(value=None, source=None, llm_confidence=0.0)
    raw = flat.get("value")
    value = parser(raw) if parser else raw
    page = flat.get("page")
    snippet = flat.get("snippet")
    conf = float(flat.get("confidence") or 0.0)
    source = SourceRef(page=page, snippet=snippet) if page else None
    return Field(value=value, source=source, llm_confidence=conf)


def parse_flat(data: dict[str, Any], doc_id: str) -> InvoiceDoc:
    """Convert the flattened tool input dict into an InvoiceDoc."""
    line_items_raw = data.get("line_items") or []
    line_items: list[LineItem] = []
    for li in line_items_raw:
        if not isinstance(li, dict):
            continue
        line_items.append(
            LineItem(
                description=_to_field(li.get("description")),
                quantity=_to_field(li.get("quantity"), _parse_dec),
                unit_price=_to_field(li.get("unit_price"), _parse_dec),
                amount=_to_field(li.get("amount"), _parse_dec),
            )
        )

    doc_kind_flat = data.get("doc_kind")
    if isinstance(doc_kind_flat, dict):
        kind_val = doc_kind_flat.get("value")
        kind_val = kind_val if kind_val in ("invoice", "purchase_order") else "invoice"
        doc_kind = _to_field(doc_kind_flat)
        doc_kind.value = kind_val
    else:
        doc_kind = Field(value="invoice", llm_confidence=0.5)

    return InvoiceDoc(
        doc_id=doc_id,
        doc_kind=doc_kind,
        supplier_name=_to_field(data.get("supplier_name")),
        supplier_tax_id=_to_field(data.get("supplier_tax_id")),
        document_number=_to_field(data.get("document_number")),
        issue_date=_to_field(data.get("issue_date"), _parse_date),
        due_date=_to_field(data.get("due_date"), _parse_date),
        currency=_to_field(data.get("currency"), lambda v: str(v).upper() if v else None),
        line_items=line_items,
        subtotal=_to_field(data.get("subtotal"), _parse_dec),
        tax_total=_to_field(data.get("tax_total"), _parse_dec),
        total=_to_field(data.get("total"), _parse_dec),
    )


def _flat_field(f: Field) -> dict:
    v = f.value
    if isinstance(v, Decimal):
        v = float(v)
    elif isinstance(v, date):
        v = v.isoformat()
    return {
        "value": v,
        "page": f.source.page if f.source else None,
        "snippet": f.source.snippet if f.source else None,
        "confidence": f.llm_confidence,
    }


def affected_previous_fields(doc: InvoiceDoc, issue_paths: set[str]) -> list[dict]:
    """Previous values for the fields named in issues (flattened)."""
    out = []

    def add(path: str, f: Field):
        if path in issue_paths:
            d = _flat_field(f)
            d["field_path"] = path
            out.append(d)

    for name in (
        "doc_kind", "supplier_name", "supplier_tax_id", "document_number",
        "issue_date", "due_date", "currency", "subtotal", "tax_total", "total",
    ):
        add(name, getattr(doc, name))
    for i, li in enumerate(doc.line_items):
        for sub in ("description", "quantity", "unit_price", "amount"):
            add(f"line_items[{i}].{sub}", getattr(li, sub))
    return out


def _set_field_by_path(doc: InvoiceDoc, path: str, flat: dict) -> None:
    parser = None
    if path in ("issue_date", "due_date"):
        parser = _parse_date
    elif path in ("subtotal", "tax_total", "total"):
        parser = _parse_dec
    elif path.endswith(".quantity") or path.endswith(".unit_price") or path.endswith(".amount"):
        parser = _parse_dec
    elif path == "currency":
        parser = lambda v: str(v).upper() if v else None

    if path.startswith("line_items[") and "]" in path:
        idx_s, rest = path[len("line_items["):].split("]", 1)
        idx = int(idx_s)
        rest = rest.lstrip(".")
        if 0 <= idx < len(doc.line_items) and rest:
            f = getattr(doc.line_items[idx], rest)
            new = _to_field(flat, parser)
            setattr(doc.line_items[idx], rest, new)
        return
    if hasattr(doc, path):
        f = getattr(doc, path)
        new = _to_field(flat, parser)
        setattr(doc, path, new)


def apply_corrections(doc: InvoiceDoc, update_data: dict[str, Any]) -> None:
    """Merge a record_correction tool input back into the doc."""
    updates = update_data.get("fields_to_update") or []
    for u in updates:
        if not isinstance(u, dict):
            continue
        path = u.get("field_path")
        if not path:
            continue
        _set_field_by_path(doc, path, u)


def extract(
    llm,
    doc_id: str,
    doc_type: str,
    marked_text: str,
) -> tuple[InvoiceDoc, Usage]:
    """One extraction call. Returns (InvoiceDoc, usage)."""
    user = EXTRACT_USER.format(doc_type=doc_type, marked_text=marked_text)
    data, usage = llm.call_tool(EXTRACT_SYSTEM, user, INVOICE_TOOL, TOOL_NAME)
    doc = parse_flat(data, doc_id)
    return doc, usage


def correct(
    llm,
    doc: InvoiceDoc,
    doc_type: str,
    marked_text: str,
    issues: list,
) -> Usage:
    """Targeted correction call. Mutates doc. Returns usage of this call."""
    issue_paths = fields_with_issues(issues)
    issue_lines = "\n".join(f"- [{i.code}] {i.field_path}: {i.message}" for i in issues)
    prev = affected_previous_fields(doc, issue_paths)
    user = CORRECTION_USER.format(
        issues=issue_lines,
        previous_fields=json.dumps(prev, indent=2, default=str),
        marked_text=marked_text,
    )
    data, usage = llm.call_tool(CORRECTION_SYSTEM, user, CORRECTION_TOOL, "record_correction")
    apply_corrections(doc, data)
    return usage
