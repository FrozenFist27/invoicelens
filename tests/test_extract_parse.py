"""Parsing + correction-merge helpers in extract.py."""

from datetime import date
from decimal import Decimal

from invoicelens.extract import _parse_date, _parse_dec, apply_corrections, parse_flat


def fv(v, page="p1", conf=0.9):
    return {"value": v, "page": page, "snippet": "s", "confidence": conf}


def _flat():
    return {
        "doc_kind": fv("purchase_order"),
        "supplier_name": fv("ACME"),
        "supplier_tax_id": fv(None, conf=0),
        "document_number": fv("PO-1"),
        "issue_date": fv("2026-03-04"),
        "due_date": fv("4 March 2026"),
        "currency": fv("usd"),
        "line_items": [
            {"description": fv("A"), "quantity": fv("2"), "unit_price": fv("1,000.50"), "amount": fv("2001.00")},
            "not-a-dict",
        ],
        "subtotal": fv(2001.0),
        "tax_total": fv(None, conf=0),
        "total": fv("2001"),
    }


def test_parse_flat_types_and_normalisation():
    doc = parse_flat(_flat(), "d1")
    assert doc.doc_kind.value == "purchase_order"
    assert doc.issue_date.value == date(2026, 3, 4)
    assert doc.due_date.value == date(2026, 3, 4)
    assert doc.currency.value == "USD"
    assert len(doc.line_items) == 1  # the malformed entry is skipped
    assert doc.line_items[0].unit_price.value == Decimal("1000.50")
    assert doc.total.source.page == "p1"


def test_parse_flat_defaults_when_fields_missing():
    flat = _flat()
    flat["doc_kind"] = None
    flat["supplier_name"] = None
    doc = parse_flat(flat, "d2")
    assert doc.doc_kind.value == "invoice"
    assert doc.supplier_name.value is None and doc.supplier_name.llm_confidence == 0.0


def test_parsers_reject_garbage():
    assert _parse_date("not a date") is None
    assert _parse_date(None) is None
    assert _parse_dec("abc") is None
    assert _parse_dec(None) is None
    assert _parse_dec("1,234.50") == Decimal("1234.50")


def test_apply_corrections_scalar_and_line_item_paths():
    doc = parse_flat(_flat(), "d3")
    apply_corrections(
        doc,
        {
            "fields_to_update": [
                {"field_path": "total", "value": "2100.00", "page": "p1", "snippet": "t", "confidence": 0.8},
                {"field_path": "issue_date", "value": "2026-04-05", "page": "p1", "snippet": "d", "confidence": 0.8},
                {"field_path": "line_items[0].amount", "value": 1999.5, "page": "p1", "snippet": "a", "confidence": 0.7},
                {"field_path": "currency", "value": "eur", "page": "p1", "snippet": "c", "confidence": 0.9},
                {"field_path": "line_items[9].amount", "value": 1, "page": "p1", "snippet": "x", "confidence": 0.1},
                {"field_path": "", "value": 1},
                "junk",
            ]
        },
    )
    assert doc.total.value == Decimal("2100.00")
    assert doc.issue_date.value == date(2026, 4, 5)
    assert doc.line_items[0].amount.value == Decimal("1999.5")
    assert doc.currency.value == "EUR"
