"""Minimal FastAPI demo: upload page, result view with source links, review queue.

Demo caps (config/settings.yaml `demo:` / env DEMO_*): max upload size, max PDF pages, global
daily document limit, per-IP rate limit. The "sample documents" buttons replay cached real
results (data/samples/*.json) and cost nothing.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import uuid
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ..settings import PROJECT_ROOT, get_settings

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app = FastAPI(title="InvoiceLens demo")

SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
SYN_DIR = PROJECT_ROOT / "data" / "synthetic"
WORK_DIR = Path(tempfile.gettempdir()) / "invoicelens_web"
ALLOWED = {".pdf", ".xlsx", ".csv", ".eml"}
SESSION_TTL_S = 1800
PER_IP_PER_MIN = 5

_daily = {"day": date.today(), "n": 0}
_ip_hits: dict[str, deque] = defaultdict(deque)
_results: dict[str, dict] = {}  # session id -> {"result": dict, "path": Path|None, "ts": float}


def _caps():
    cfg = get_settings()
    return {
        "max_mb": cfg.demo.max_upload_mb,
        "max_pages": cfg.demo_max_pages,
        "daily": cfg.demo_daily_doc_limit,
    }


def _sweep() -> None:
    """Delete uploads (and their cached results) older than the session TTL."""
    now = time.time()
    for sid in [k for k, v in _results.items() if now - v["ts"] > SESSION_TTL_S]:
        _results.pop(sid, None)
        shutil.rmtree(WORK_DIR / sid, ignore_errors=True)


def _check_limits(request: Request) -> None:
    caps = _caps()
    if _daily["day"] != date.today():
        _daily.update(day=date.today(), n=0)
    if _daily["n"] >= caps["daily"]:
        raise HTTPException(429, f"Daily demo limit of {caps['daily']} documents reached. Try the cached samples.")
    ip = request.client.host if request.client else "?"
    q = _ip_hits[ip]
    now = time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= PER_IP_PER_MIN:
        raise HTTPException(429, "Rate limit: too many uploads from this address. Wait a minute.")
    q.append(now)


def _sample_list() -> list[dict]:
    out = []
    if SAMPLES_DIR.exists():
        for p in sorted(SAMPLES_DIR.glob("*.json")):
            meta = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": p.stem, "doc_type": meta.get("_doc_type", "?"), "note": meta.get("_note", "")})
    return out


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"caps": _caps(), "samples": _sample_list(), "error": None}
    )


@app.post("/extract", response_class=HTMLResponse)
async def extract_upload(request: Request, file: UploadFile = File(...)):
    _sweep()
    caps = _caps()
    name = Path(file.filename or "upload").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, f"Unsupported file type {ext!r}. Use PDF, XLSX, CSV or EML.")
    data = await file.read()
    if len(data) > caps["max_mb"] * 1024 * 1024:
        raise HTTPException(413, f"File larger than {caps['max_mb']} MB demo cap.")
    _check_limits(request)

    sid = uuid.uuid4().hex[:12]
    wd = WORK_DIR / sid
    wd.mkdir(parents=True, exist_ok=True)
    path = wd / f"{sid}{ext}"
    path.write_bytes(data)

    if ext == ".pdf":
        import pymupdf

        try:
            n_pages = pymupdf.open(path).page_count
        except Exception:  # noqa: BLE001
            shutil.rmtree(wd, ignore_errors=True)
            raise HTTPException(400, "Could not read this PDF.") from None
        if n_pages > caps["max_pages"]:
            shutil.rmtree(wd, ignore_errors=True)
            raise HTTPException(413, f"PDF has {n_pages} pages; demo cap is {caps['max_pages']}.")

    from ..cli import _get_llm
    from ..pipeline import process_document
    from ..review_queue import init_db
    from ..writer import doc_to_dict

    init_db()
    try:
        llm = _get_llm()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"LLM not configured: {e}") from None
    _daily["n"] += 1
    results = process_document(llm, path, config="full", doc_id=sid, include_attachments=False)
    r = results[0]
    if r.error or r.doc is None:
        raise HTTPException(502, f"Extraction failed: {r.error}")
    payload = doc_to_dict(r.doc)
    payload["_doc_type"] = r.doc_type
    payload["_metrics"] = r.metrics.model_dump() if r.metrics else {}
    payload["_issues"] = [i.model_dump() for i in r.issues]
    _results[sid] = {"result": payload, "path": path, "ts": time.time(), "filename": name}
    return _render_result(request, sid)


@app.post("/sample/{doc_id}", response_class=HTMLResponse)
def sample(request: Request, doc_id: str):
    p = SAMPLES_DIR / f"{Path(doc_id).name}.json"
    if not p.exists():
        raise HTTPException(404, "Unknown sample")
    payload = json.loads(p.read_text(encoding="utf-8"))
    sid = f"sample-{p.stem}"
    src = next((q for q in SYN_DIR.glob(f"{p.stem}.*") if q.suffix.lower() in ALLOWED), None)
    _results[sid] = {
        "result": payload,
        "path": src,
        "ts": time.time() + 10**9,  # never swept; samples are static
        "filename": src.name if src else p.stem,
    }
    return _render_result(request, sid, cached=True)


def _flatten(payload: dict) -> list[dict]:
    rows = []
    for k in (
        "doc_kind", "supplier_name", "supplier_tax_id", "document_number", "issue_date",
        "due_date", "currency", "subtotal", "tax_total", "total",
    ):
        rows.append({"path": k, **payload[k]})
    for i, li in enumerate(payload.get("line_items", [])):
        for s in ("description", "quantity", "unit_price", "amount"):
            rows.append({"path": f"line_items[{i}].{s}", **li[s]})
    return rows


def _render_result(request: Request, sid: str, cached: bool = False):
    entry = _results[sid]
    payload = entry["result"]
    rows = [r for r in _flatten(payload) if r["value"] is not None]
    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "sid": sid,
            "filename": entry.get("filename"),
            "rows": rows,
            "doc_type": payload.get("_doc_type"),
            "metrics": payload.get("_metrics") or {},
            "issues": payload.get("_issues") or [],
            "cached": cached,
            "raw": json.dumps({k: v for k, v in payload.items() if not k.startswith("_")}, indent=2),
        },
    )


@app.get("/source/{sid}", response_class=HTMLResponse)
def source_view(request: Request, sid: str, page: str = "p1", snippet: str = ""):
    entry = _results.get(sid)
    if not entry or not entry.get("path"):
        raise HTTPException(404, "Source no longer available (uploads are deleted after 30 minutes).")
    path: Path = entry["path"]
    text = None
    if path.suffix.lower() != ".pdf":
        from ..pipeline import MARKERS, _load

        doc_text, _ = _load(path, sid)
        text = MARKERS[doc_text.doc_type](doc_text)
    return templates.TemplateResponse(
        request,
        "source.html",
        {"sid": sid, "page": page, "snippet": snippet, "text": text, "is_pdf": text is None},
    )


@app.get("/source/{sid}/page.png")
def source_png(sid: str, page: str = "p1", snippet: str = ""):
    entry = _results.get(sid)
    if not entry or not entry.get("path") or entry["path"].suffix.lower() != ".pdf":
        raise HTTPException(404)
    import pymupdf

    doc = pymupdf.open(entry["path"])
    try:
        n = int(page.lstrip("p")) - 1
    except ValueError:
        n = 0
    n = max(0, min(n, doc.page_count - 1))
    pg = doc[n]
    for line in [s for s in snippet.splitlines() if s.strip()][:3]:
        for rect in pg.search_for(line.strip()[:80]):
            pg.add_highlight_annot(rect)
    pix = pg.get_pixmap(dpi=110)
    return Response(pix.tobytes("png"), media_type="image/png")


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request):
    from ..review_queue import init_db, list_pending

    init_db()
    return templates.TemplateResponse(request, "review.html", {"items": list_pending()})


@app.post("/review/{item_id}")
def review_action(item_id: int, action: str = Form(...), value: str = Form("")):
    from ..review_queue import accept, correct_item

    if action == "accept":
        accept(item_id)
    elif action == "correct" and value.strip():
        correct_item(item_id, value.strip())
    else:
        raise HTTPException(400, "bad action")
    return RedirectResponse("/review", status_code=303)


@app.get("/health")
def health():
    return {"ok": True, "daily_used": _daily["n"], "caps": _caps()}
