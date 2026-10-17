"""Retry / correction tests with FakeLLMClient (IDEATION section 12)."""


from invoicelens.extract import extract
from invoicelens.llm.fake_client import FakeLLMClient
from invoicelens.validate import validate_doc


def _valid_flat(total="22.00", tax="2.00", subtotal="20.00"):
    def fv(v, page="p1", conf=0.9):
        return {"value": v, "page": page, "snippet": "x", "confidence": conf}

    return {
        "doc_kind": fv("invoice"),
        "supplier_name": fv("ACME"),
        "supplier_tax_id": fv(None, conf=0),
        "document_number": fv("INV-1"),
        "issue_date": fv("2026-03-04"),
        "due_date": fv("2026-04-03"),
        "currency": fv("USD"),
        "line_items": [
            {
                "description": fv("Widget"),
                "quantity": fv(2),
                "unit_price": fv(10.0),
                "amount": fv(20.0),
            }
        ],
        "subtotal": fv(subtotal),
        "tax_total": fv(tax),
        "total": fv(total),
    }


def _invalid_flat():
    # total wrong -> arith_total issue
    return _valid_flat(total="99.99")


def test_valid_first_time_zero_retries():
    llm = FakeLLMClient(script=[_valid_flat()])
    doc, _ = extract(llm, "d1", "text_pdf", "[p1] ACME INV-1")
    issues = validate_doc(doc)
    assert issues == []
    assert len(llm.calls) == 1


def test_invalid_then_valid_one_retry():
    correction = {
        "fields_to_update": [
            {"field_path": "total", "value": 22.00, "page": "p1", "snippet": "TOTAL 22.00", "confidence": 0.9}
        ]
    }
    llm = FakeLLMClient(script=[_invalid_flat(), correction])
    doc, _ = extract(llm, "d1", "text_pdf", "[p1] text")
    issues = validate_doc(doc)
    assert issues
    from invoicelens.extract import correct

    correct(llm, doc, "text_pdf", "[p1] text", issues)
    issues2 = validate_doc(doc)
    assert issues2 == []
    assert len(llm.calls) == 2


def test_always_invalid_stops_at_max():
    llm = FakeLLMClient(script=[_invalid_flat(), _invalid_flat(), _invalid_flat(), _invalid_flat()])
    doc, _ = extract(llm, "d1", "text_pdf", "[p1] text")
    issues = validate_doc(doc)
    retries = 0
    max_retries = 2
    from invoicelens.extract import correct

    while issues and retries < max_retries:
        correct(llm, doc, "text_pdf", "[p1] text", issues)
        retries += 1
        issues = validate_doc(doc)
    assert retries == 2
    assert issues  # still invalid


def test_correction_prompt_contains_only_failing_fields():
    llm = FakeLLMClient(script=[_invalid_flat(), _valid_flat()])
    doc, _ = extract(llm, "d1", "text_pdf", "[p1] text")
    issues = validate_doc(doc)
    from invoicelens.extract import correct

    correct(llm, doc, "text_pdf", "[p1] text", issues)
    correction_call = llm.calls[-1]
    assert "total" in correction_call["user"]
    # supplier_name is valid, so it should not be in the previous-fields list
    assert "supplier_name" not in correction_call["user"]


def test_inconsistent_source_not_forced():
    # Source total is 99.99 but maths says 22.00; correction must keep source, lower confidence.
    llm = FakeLLMClient(
        script=[
            _valid_flat(total="99.99"),
            {
                "fields_to_update": [
                    {"field_path": "total", "value": 99.99, "page": "p1", "snippet": "TOTAL 99.99", "confidence": 0.3}
                ]
            },
        ]
    )
    doc, _ = extract(llm, "d1", "text_pdf", "[p1] text")
    issues = validate_doc(doc)
    from invoicelens.extract import correct

    correct(llm, doc, "text_pdf", "[p1] text", issues)
    assert float(doc.total.value) == 99.99  # kept source value
    assert doc.total.llm_confidence < 0.5  # low confidence, not forced
