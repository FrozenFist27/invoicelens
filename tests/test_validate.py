"""Validation rule tests (IDEATION section 12)."""

from datetime import date
from decimal import Decimal

from invoicelens.models import Field, InvoiceDoc, LineItem, SourceRef
from invoicelens.validate import (
    check_arith_line,
    check_arith_subtotal,
    check_arith_total,
    check_currency,
    check_date_format,
    check_date_order,
    check_missing_required,
    validate_doc,
)


def _f(v, conf=0.9):
    return Field(value=v, source=SourceRef(page="p1", snippet="x"), llm_confidence=conf)


def _li(q="2", u="10.00", a="20.00", desc="Widget"):
    return LineItem(
        description=_f(desc),
        quantity=_f(Decimal(q)),
        unit_price=_f(Decimal(u)),
        amount=_f(Decimal(a)),
    )


def _doc(**kw):
    base = dict(
        doc_id="d1",
        doc_kind=_f("invoice"),
        supplier_name=_f("ACME"),
        supplier_tax_id=_f(None),
        document_number=_f("INV-1"),
        issue_date=_f(date(2026, 3, 4)),
        due_date=_f(date(2026, 4, 3)),
        currency=_f("USD"),
        line_items=[_li()],
        subtotal=_f(Decimal("20.00")),
        tax_total=_f(Decimal("2.00")),
        total=_f(Decimal("22.00")),
    )
    base.update(kw)
    return InvoiceDoc(**base)


def test_arith_line_ok():
    assert check_arith_line(_li(), 0) is None


def test_arith_line_tolerance_edge_0_01():
    # amount off by exactly 0.01 -> within abs tol
    assert check_arith_line(_li(a="20.01"), 0) is None


def test_arith_line_fails_beyond_tolerance():
    # 22.00 vs expected 20.00: 2.00 > 0.01 abs and > 0.5% relative
    assert check_arith_line(_li(a="22.00"), 0) is not None


def test_arith_subtotal_ok():
    assert check_arith_subtotal(_doc()) is None


def test_arith_subtotal_fails():
    d = _doc(subtotal=_f(Decimal("25.00")))
    assert check_arith_subtotal(d) is not None


def test_arith_total_ok():
    assert check_arith_total(_doc()) is None


def test_arith_total_null_tax_equal_subtotal():
    d = _doc(tax_total=_f(None), total=_f(Decimal("20.00")))
    assert check_arith_total(d) is None


def test_arith_total_null_tax_unequal():
    d = _doc(tax_total=_f(None), total=_f(Decimal("22.00")))
    assert check_arith_total(d) is not None


def test_date_order_ok():
    assert check_date_order(_doc()) is None


def test_date_order_fails():
    d = _doc(due_date=_f(date(2026, 3, 1)))
    assert check_date_order(d) is not None


def test_date_format_bad_year():
    d = _doc(issue_date=_f(date(1800, 1, 1)))
    assert any(i.code == "date_format" for i in check_date_format(d))


def test_currency_ok():
    assert check_currency(_doc()) is None


def test_currency_bad():
    d = _doc(currency=_f("XYZ"))
    assert check_currency(d) is not None


def test_missing_required():
    d = _doc(document_number=_f(None))
    assert any(i.field_path == "document_number" for i in check_missing_required(d))


def test_validate_doc_empty_issues():
    assert validate_doc(_doc()) == []
