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


# ---- public-demo isolation (DEMO_MODE) ----


def _doc_needing_review(doc_id="dX"):
    from invoicelens.models import Field, InvoiceDoc, SourceRef

    def f(v, st="ok"):
        return Field(value=v, source=SourceRef(page="p1", snippet="s"), llm_confidence=0.5,
                     confidence=0.4, status=st)

    doc = InvoiceDoc(
        doc_id=doc_id, doc_kind=f("invoice"), supplier_name=f("A", "needs_review"),
        supplier_tax_id=f(None), document_number=f("1"), issue_date=f(None), due_date=f(None),
        currency=f("USD"), line_items=[], subtotal=f(None), tax_total=f(None), total=f(None),
    )
    return doc


@pytest.fixture()
def demo_clients(client, monkeypatch):
    monkeypatch.setattr(webapp, "_demo", lambda: True)
    a = TestClient(webapp.app)
    b = TestClient(webapp.app)
    return a, b


def test_demo_cookie_is_httponly_lax_random(demo_clients):
    a, b = demo_clients
    ra = a.get("/review")
    set_cookie = ra.headers["set-cookie"].lower()
    assert "il_session=" in set_cookie and "httponly" in set_cookie and "samesite=lax" in set_cookie
    b.get("/review")
    assert a.cookies.get("il_session") != b.cookies.get("il_session")


def test_demo_review_queue_is_isolated_between_sessions(demo_clients):
    from invoicelens.review_queue import add_items, list_pending

    a, b = demo_clients
    a.get("/review")
    b.get("/review")
    ida = add_items(_doc_needing_review("docA"), [], session=a.cookies["il_session"])[0]
    idb = add_items(_doc_needing_review("docB"), [], session=b.cookies["il_session"])[0]
    assert "docA" in a.get("/review").text and "docB" not in a.get("/review").text
    assert "docB" in b.get("/review").text and "docA" not in b.get("/review").text
    # B cannot act on A's item
    r = b.post(f"/review/{ida}", data={"action": "accept"}, follow_redirects=False)
    assert r.status_code == 404
    r = b.post(f"/review/{ida}", data={"action": "correct", "value": "x"}, follow_redirects=False)
    assert r.status_code == 404
    assert {p.id for p in list_pending()} == {ida, idb}
    # A can
    assert a.post(f"/review/{ida}", data={"action": "accept"}, follow_redirects=False).status_code == 303
    assert {p.id for p in list_pending()} == {idb}


def test_demo_without_cookie_sees_nothing_and_forged_cookie_ignored(demo_clients):
    from invoicelens.review_queue import add_items

    a, _ = demo_clients
    add_items(_doc_needing_review("docU"), [], session=None)  # unscoped/CLI row
    c = TestClient(webapp.app)
    assert "docU" not in c.get("/review").text
    c.cookies.set("il_session", "not-a-valid-id")
    assert "docU" not in c.get("/review").text


def test_non_demo_cli_behaviour_unchanged(client):
    from invoicelens.review_queue import add_items, list_pending

    ids = add_items(_doc_needing_review("docC"), [])
    assert "docC" in client.get("/review").text
    assert client.post(f"/review/{ids[0]}", data={"action": "accept"}, follow_redirects=False).status_code == 303
    assert list_pending() == []
    assert "set-cookie" not in client.get("/review").headers


def test_demo_uploads_not_retrievable_by_other_session(demo_clients, tmp_path, monkeypatch):
    a, b = demo_clients
    a.get("/review")
    f = tmp_path / "up.csv"
    f.write_text("a,b\n1,2\n")
    webapp._results["abc123"] = {
        "result": {}, "path": f, "ts": __import__("time").time(), "filename": "up.csv",
        "owner": a.cookies["il_session"],
    }
    assert a.get("/source/abc123").status_code != 404
    assert b.get("/source/abc123").status_code == 404
    assert b.get("/source/abc123/page.png").status_code == 404
    webapp._results.pop("abc123")


def test_demo_sweep_deletes_old_uploads_and_review_rows(demo_clients, tmp_path, monkeypatch):
    import os
    import time

    from invoicelens.review_queue import add_items, list_pending

    monkeypatch.setattr(webapp, "WORK_DIR", tmp_path / "work")
    old = webapp.WORK_DIR / "orphan"
    old.mkdir(parents=True)
    (old / "x.pdf").write_bytes(b"x")
    past = time.time() - 2 * 3600
    os.utime(old, (past, past))
    tracked = webapp.WORK_DIR / "tracked"
    tracked.mkdir()
    (tracked / "t.csv").write_text("a")
    webapp._results["tracked"] = {"result": {}, "path": tracked / "t.csv",
                                  "ts": time.time() - webapp.SESSION_TTL_S - 5, "owner": "o"}
    add_items(_doc_needing_review("old"), [], session="o")
    monkeypatch.setattr(webapp, "RETENTION_S", -1)  # everything counts as old
    webapp._sweep()
    assert not old.exists() and not tracked.exists() and "tracked" not in webapp._results
    assert list_pending() == []
