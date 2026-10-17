"""Writer tests: JSON valid, CSV has one row per field with source_page/source_link."""

import csv
import json
from datetime import date
from decimal import Decimal

from invoicelens.models import DocumentText, Field, InvoiceDoc, LineItem, Page, SourceRef
from invoicelens.writer import doc_to_dict, write


def _f(v, conf=0.9, page="p1"):
    return Field(value=v, source=SourceRef(page=page, snippet="x"), llm_confidence=conf)


def _doc():
    return InvoiceDoc(
        doc_id="d1",
        doc_kind=_f("invoice"),
        supplier_name=_f("ACME"),
        supplier_tax_id=_f(None, conf=0),
        document_number=_f("INV-1"),
        issue_date=_f(date(2026, 3, 4)),
        due_date=_f(None, conf=0),
        currency=_f("USD"),
        line_items=[
            LineItem(description=_f("Widget"), quantity=_f(Decimal("2")), unit_price=_f(Decimal("10")), amount=_f(Decimal("20")))
        ],
        subtotal=_f(Decimal("20")),
        tax_total=_f(None, conf=0),
        total=_f(Decimal("20")),
    )


def _doc_text(tmp_path):
    p = tmp_path / "d1.pdf"
    p.write_bytes(b"%PDF-1.4")
    return DocumentText(doc_id="d1", doc_type="text_pdf", pages=[Page(ref="p1", text="x")], source_path=str(p))


def test_write_json_and_csv(tmp_path):
    doc = _doc()
    dt = _doc_text(tmp_path)
    jpath, cpath = write(doc, dt, tmp_path / "out")
    data = json.loads(jpath.read_text())
    assert data["supplier_name"]["value"] == "ACME"
    assert data["supplier_name"]["source"]["page"] == "p1"

    with open(cpath, newline="") as f:
        rows = list(csv.reader(f))
    header = rows[0]
    assert "source_page" in header and "source_link" in header
    # one row per field: 10 scalars + 4 line-item subfields = 14
    assert len(rows) - 1 == 14
    # every row has a source_link
    si = header.index("source_link")
    assert all(r[si] for r in rows[1:])


def test_doc_to_dict_schema():
    d = doc_to_dict(_doc())
    assert set(d.keys()) == {
        "doc_id", "doc_kind", "supplier_name", "supplier_tax_id", "document_number",
        "issue_date", "due_date", "currency", "line_items", "subtotal", "tax_total", "total",
    }
