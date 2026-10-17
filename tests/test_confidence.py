"""Confidence scoring tests."""

from datetime import date
from decimal import Decimal

from invoicelens.confidence import grounding_score, score_doc
from invoicelens.models import DocumentText, Field, InvoiceDoc, LineItem, Page, SourceRef
from invoicelens.settings import get_settings


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
        due_date=_f(date(2026, 4, 3)),
        currency=_f("USD"),
        line_items=[
            LineItem(
                description=_f("Widget"),
                quantity=_f(Decimal("2")),
                unit_price=_f(Decimal("10.00")),
                amount=_f(Decimal("20.00")),
            )
        ],
        subtotal=_f(Decimal("20.00")),
        tax_total=_f(Decimal("2.00")),
        total=_f(Decimal("22.00")),
    )


def _doc_text(ocr=None):
    return DocumentText(
        doc_id="d1",
        doc_type="text_pdf",
        pages=[Page(ref="p1", text="ACME INV-1 2026-03-04 USD 20.00 2.00 22.00 Widget 2 10.00", ocr_confidence=ocr)],
    )


def test_grounding_exact():
    assert grounding_score("ACME", "the ACME invoice", ocr=False) == 1.0


def test_grounding_none():
    assert grounding_score("ZZZZ", "nothing here", ocr=False) == 0.0


def test_grounding_fuzzy_ocr():
    # slight OCR mismatch still >=85 fuzzy
    assert grounding_score("ACME Supplies", "ACME Suppl1es", ocr=True) == 0.6


def test_score_doc_high_confidence_ok():
    doc = _doc()
    score_doc(doc, _doc_text(), [])
    assert doc.supplier_name.status == "ok"
    assert doc.supplier_name.confidence >= 0.7
    assert doc.supplier_tax_id.confidence == 0.0  # null value


def test_score_doc_ocr_penalty():
    doc = _doc()
    score_doc(doc, _doc_text(ocr=50.0), [])  # 50/90 ~ 0.55 multiplier
    # with exact grounding 1.0 and high llm conf, but OCR penalty reduces score
    assert doc.supplier_name.confidence < 1.0


def test_score_doc_issue_forces_review():
    doc = _doc()
    score_doc(doc, _doc_text(), [type("I", (), {"field_path": "total", "code": "arith_total", "message": "x"})()])
    assert doc.total.status == "needs_review"


def test_threshold_routing():
    cfg = get_settings()
    assert cfg.review_threshold == 0.7
