"""SQLite review queue (IDEATION 4.1)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .confidence import iter_fields
from .models import InvoiceDoc, ReviewItem, ValidationIssue

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "review.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    suggested_value TEXT,
    confidence REAL,
    issues TEXT,
    source_page TEXT,
    snippet TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    corrected_value TEXT,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _conn(db_path: str | Path | None = None):
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path | None = None) -> None:
    with _conn(db_path) as conn:
        conn.executescript(SCHEMA)


def add_items(
    doc: InvoiceDoc,
    issues: list[ValidationIssue],
    db_path: str | Path | None = None,
) -> list[int]:
    """Insert one row per needs_review field. Returns new ids."""
    issue_map: dict[str, list[str]] = {}
    for i in issues:
        issue_map.setdefault(i.field_path, []).append(f"[{i.code}] {i.message}")
    ids: list[int] = []
    now = datetime.now(timezone.utc).isoformat()
    init_db(db_path)
    with _conn(db_path) as conn:
        # re-processing a document replaces its still-pending items instead of duplicating them
        conn.execute("DELETE FROM review_items WHERE doc_id=? AND status='pending'", (doc.doc_id,))
        for path, f in iter_fields(doc):
            if f.status != "needs_review":
                continue
            val = f.value
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            cur = conn.execute(
                """INSERT INTO review_items
                   (doc_id, field_path, suggested_value, confidence, issues, source_page, snippet, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    doc.doc_id,
                    path,
                    str(val) if val is not None else None,
                    f.confidence,
                    "\n".join(issue_map.get(path, [])),
                    f.source.page if f.source else None,
                    f.source.snippet if f.source else None,
                    "pending",
                    now,
                ),
            )
            ids.append(cur.lastrowid)
    return ids


def list_pending(db_path: str | Path | None = None) -> list[ReviewItem]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM review_items WHERE status='pending' ORDER BY id"
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def accept(item_id: int, db_path: str | Path | None = None) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE review_items SET status='accepted', corrected_value=suggested_value WHERE id=?",
            (item_id,),
        )


def correct_item(item_id: int, value: str, db_path: str | Path | None = None) -> None:
    with _conn(db_path) as conn:
        conn.execute(
            "UPDATE review_items SET status='corrected', corrected_value=? WHERE id=?",
            (value, item_id),
        )


def _row_to_item(r) -> ReviewItem:
    issues = [s for s in (r["issues"] or "").split("\n") if s]
    return ReviewItem(
        id=r["id"],
        doc_id=r["doc_id"],
        field_path=r["field_path"],
        suggested_value=r["suggested_value"],
        confidence=r["confidence"],
        issues=issues,
        source_page=r["source_page"],
        snippet=r["snippet"],
        status=r["status"],
        corrected_value=r["corrected_value"],
        created_at=datetime.fromisoformat(r["created_at"]),
    )
