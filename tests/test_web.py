"""Web demo tests: caps, cached samples, review actions. No network / no LLM."""

import json

import pytest
from fastapi.testclient import TestClient

from invoicelens.web import app as webapp


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("invoicelens.review_queue.DEFAULT_DB", tmp_path / "review.db")
    webapp._daily.update(n=0)
    webapp._ip_hits.clear()
    return TestClient(webapp.app)


def test_index_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["ok"] is True


def test_rejects_bad_extension(client):
    r = client.post("/extract", files={"file": ("x.exe", b"abc", "application/octet-stream")})
    assert r.status_code == 400


def test_rejects_oversize(client):
    big = b"0" * (3 * 1024 * 1024)
    r = client.post("/extract", files={"file": ("x.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_rejects_too_many_pages(client, tmp_path):
    import pymupdf

    d = pymupdf.open()
    for _ in range(5):
        d.new_page().insert_text((72, 72), "hello")
    r = client.post("/extract", files={"file": ("x.pdf", d.tobytes(), "application/pdf")})
    assert r.status_code == 413
    assert "pages" in r.json()["detail"]


def test_daily_limit(client):
    webapp._daily["n"] = 10**6
    r = client.post("/extract", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert r.status_code == 429


def test_cached_sample_replay_and_review_flow(client, tmp_path, monkeypatch):
    sdir = tmp_path / "samples"
    sdir.mkdir()

    def fld(v, status="ok"):
        return {"value": v, "source": {"page": "p1", "snippet": "x"}, "llm_confidence": 0.9,
                "confidence": 0.9, "status": status}

    payload = {
        "_doc_type": "text_pdf", "doc_id": "zz", "doc_kind": fld("invoice"),
        "supplier_name": fld("ACME"), "supplier_tax_id": fld(None), "document_number": fld("INV-1"),
        "issue_date": fld("2026-01-01"), "due_date": fld(None), "currency": fld("USD"),
        "line_items": [], "subtotal": fld(None), "tax_total": fld(None),
        "total": fld("10.00", "needs_review"),
    }
    (sdir / "zz.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(webapp, "SAMPLES_DIR", sdir)
    r = client.post("/sample/zz")
    assert r.status_code == 200 and "ACME" in r.text and "needs_review" in r.text
    assert client.post("/sample/nope").status_code == 404


def test_review_accept_and_correct(client):
    from invoicelens.models import Field, InvoiceDoc, SourceRef
    from invoicelens.review_queue import add_items, list_pending

    def f(v, st="ok"):
        return Field(value=v, source=SourceRef(page="p1", snippet="s"), llm_confidence=0.5,
                     confidence=0.4, status=st)

    doc = InvoiceDoc(
        doc_id="d1", doc_kind=f("invoice"), supplier_name=f("A"), supplier_tax_id=f(None),
        document_number=f("1"), issue_date=f(None), due_date=f(None), currency=f("USD"),
        line_items=[], subtotal=f(None), tax_total=f(None), total=f(None, "needs_review"),
    )
    doc.supplier_name.status = "needs_review"
    ids = add_items(doc, [])
    assert len(ids) >= 1
    assert client.get("/review").status_code == 200
    r = client.post(f"/review/{ids[0]}", data={"action": "accept"}, follow_redirects=False)
    assert r.status_code == 303
    pending = list_pending()
    assert all(p.id != ids[0] for p in pending)
    # re-adding the same doc replaces its pending rows instead of duplicating them
    before = len(list_pending())
    add_items(doc, [])
    add_items(doc, [])
    assert len(list_pending()) <= before + len(ids)
