"""Copy real, already-measured extraction results into data/samples/ for the zero-cost demo replay.

Reads reports/preds_full_<split>.json (written by `invoicelens eval --config full`), so every cached
sample is a genuine pipeline output, not hand-written. Usage: python scripts/make_samples.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# doc_id -> short note shown on the demo button
PICKS = {
    "doc_016": ("text PDF", "text_pdf"),
    "doc_034": ("scanned PDF (OCR)", "scanned_pdf"),
    "doc_022": ("spreadsheet", "spreadsheet"),
    "doc_024": ("email + PDF attachment", "email"),
    "doc_012": ("European number format", "text_pdf"),
}


def main() -> None:
    out = ROOT / "data" / "samples"
    out.mkdir(parents=True, exist_ok=True)
    preds: dict[str, dict] = {}
    for split in ("heldout", "dev"):
        f = ROOT / "reports" / f"preds_full_{split}.json"
        if f.exists():
            preds.update(json.loads(f.read_text(encoding="utf-8")))
    for doc_id, (note, dtype) in PICKS.items():
        if doc_id not in preds or not preds[doc_id]:
            print(f"skip {doc_id}: no prediction available")
            continue
        payload = dict(preds[doc_id])
        payload["_doc_type"] = dtype
        payload["_note"] = note
        (out / f"{doc_id}.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
        print("wrote", doc_id)


if __name__ == "__main__":
    main()
