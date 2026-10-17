"""End-to-end pipeline tests with FakeLLMClient, one fixture of each of 4 types."""

from invoicelens.llm.fake_client import FakeLLMClient
from invoicelens.pipeline import process_document


def _flat(total="22.00", tax="2.00", subtotal="20.00", supplier="ACME Supplies Ltd"):
    def fv(v, page="p1", conf=0.9):
        return {"value": v, "page": page, "snippet": "x", "confidence": conf}

    return {
        "doc_kind": fv("invoice"),
        "supplier_name": fv(supplier),
        "supplier_tax_id": fv(None, conf=0),
        "document_number": fv("INV-1001"),
        "issue_date": fv("2026-03-04"),
        "due_date": fv(None, conf=0),
        "currency": fv("USD"),
        "line_items": [
            {"description": fv("Widget"), "quantity": fv(2), "unit_price": fv(10.0), "amount": fv(20.0)}
        ],
        "subtotal": fv(subtotal),
        "tax_total": fv(tax),
        "total": fv(total),
    }


def test_pipeline_text_pdf(fixtures_dir, tmp_path):
    llm = FakeLLMClient(script=[_flat()])
    results = process_document(llm, fixtures_dir / "text.pdf", config="full", doc_id="t1", write_outputs=True, out_dir=tmp_path)
    r = results[0]
    assert r.error is None
    assert r.doc.supplier_name.value == "ACME Supplies Ltd"
    assert r.metrics.cost_usd > 0  # fake usage is billed at model rate (tiny)
    assert (tmp_path / "t1.json").exists()


def test_pipeline_spreadsheet(fixtures_dir, tmp_path):
    llm = FakeLLMClient(script=[_flat()])
    results = process_document(llm, fixtures_dir / "sheet.xlsx", config="full", doc_id="s1", write_outputs=True, out_dir=tmp_path)
    r = results[0]
    assert r.error is None
    assert r.doc_type == "spreadsheet"


def test_pipeline_email(fixtures_dir, tmp_path):
    llm = FakeLLMClient(script=[_flat()])
    results = process_document(llm, fixtures_dir / "mail.eml", config="full", doc_id="e1", write_outputs=True, out_dir=tmp_path)
    r = results[0]
    assert r.error is None
    assert r.doc_type == "email"


def test_pipeline_scanned_pdf(fixtures_dir, tmp_path):
    # scanned fixture is image-only; OCR returns empty text -> LLM still returns scripted flat
    llm = FakeLLMClient(script=[_flat()])
    results = process_document(llm, fixtures_dir / "scanned.pdf", config="baseline", doc_id="sc1", write_outputs=True, out_dir=tmp_path)
    r = results[0]
    # may error if tesseract missing, but should succeed on this machine
    assert r.error is None
    assert r.doc_type == "scanned_pdf"


def test_pipeline_baseline_no_review(fixtures_dir, tmp_path):
    llm = FakeLLMClient(script=[_flat(total="99.99")])
    results = process_document(llm, fixtures_dir / "text.pdf", config="baseline", doc_id="b1")
    r = results[0]
    assert r.metrics.retries == 0
