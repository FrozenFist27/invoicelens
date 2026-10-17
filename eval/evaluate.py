"""Evaluation runner: baseline vs full on a split, per-field P/R, cost/time, review routing.

Writes reports/eval_{config}.json and reports/eval_report.md (when write_report=True).
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from matching import (
    match_currency,
    match_date,
    match_doc_number,
    match_line_items,
    match_money,
    match_supplier,
    match_bool,
    prf,
)

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "data" / "synthetic"
LABELS = ROOT / "data" / "labels"
REPORTS = ROOT / "reports"


def _find_file(doc_id: str) -> Path | None:
    for ext in (".pdf", ".xlsx", ".csv", ".eml"):
        p = SYN / f"{doc_id}{ext}"
        if p.exists():
            return p
    return None


def _field_value(pred_field):
    if isinstance(pred_field, dict):
        return pred_field.get("value")
    return pred_field


def _field_status(pred_field):
    if isinstance(pred_field, dict):
        return pred_field.get("status", "ok")
    return "ok"


def _field_page(pred_field):
    if isinstance(pred_field, dict):
        src = pred_field.get("source")
        if isinstance(src, dict):
            return src.get("page")
    return None


def score_doc(pred_doc: dict | None, label: dict, config: str) -> dict:
    """Score one predicted doc against its label. Returns counters per field."""
    fields = {
        "supplier_name": [], "document_number": [], "issue_date": [], "due_date": [],
        "currency": [], "doc_kind": [], "subtotal": [], "tax_total": [], "total": [],
        "line_items.*": [],
    }
    if pred_doc is None:
        # everything non-null in the label is FN
        for k in ("supplier_name", "document_number", "issue_date", "due_date", "currency", "doc_kind", "subtotal", "tax_total", "total"):
            if label.get(k) is not None:
                fields[k].append(("fn", None))
        if label.get("line_items"):
            fields["line_items.*"].append(("fn", None))
        return fields

    checks = [
        ("supplier_name", match_supplier),
        ("document_number", match_doc_number),
        ("issue_date", match_date),
        ("due_date", match_date),
        ("currency", match_currency),
        ("doc_kind", match_bool),
        ("subtotal", match_money),
        ("tax_total", match_money),
        ("total", match_money),
    ]
    for key, matcher in checks:
        pv = _field_value(pred_doc.get(key))
        lv = label.get(key)
        if lv is None and pv is None:
            continue
        if lv is not None and pv is None:
            fields[key].append(("fn", _field_status(pred_doc.get(key))))
            continue
        if lv is None and pv is not None:
            fields[key].append(("fp", _field_status(pred_doc.get(key))))
            continue
        ok = matcher(pv, lv)
        fields[key].append(("tp" if ok else "fp", _field_status(pred_doc.get(key))))
        if not ok:
            fields[key].append(("fn", _field_status(pred_doc.get(key))))  # wrong counts as both FP and FN

    li = match_line_items(pred_doc.get("line_items") or [], label.get("line_items") or [])
    for _ in range(li["tp"]):
        fields["line_items.*"].append(("tp", None))
    for _ in range(li["fp"]):
        fields["line_items.*"].append(("fp", None))
    for _ in range(li["fn"]):
        fields["line_items.*"].append(("fn", None))
    return fields


def _traceability(pred_doc: dict | None, label: dict) -> tuple[int, int]:
    """(correct_page, total_with_page) over non-null predicted scalar fields."""
    if pred_doc is None:
        return 0, 0
    pages = label.get("source_pages", {})
    correct = total = 0
    for key in (
        "supplier_name", "document_number", "issue_date", "due_date",
        "currency", "doc_kind", "subtotal", "tax_total", "total",
    ):
        pv = _field_value(pred_doc.get(key))
        page = _field_page(pred_doc.get(key))
        if pv is None or page is None:
            continue
        total += 1
        if pages.get(key) == page:
            correct += 1
    return correct, total


def run_eval(config: str = "full", split: str = "heldout", limit: int = 0, write_report: bool = True) -> dict:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from invoicelens.llm.anthropic_client import AnthropicClient
    from invoicelens.pipeline import process_document
    from invoicelens.review_queue import init_db
    from invoicelens.writer import doc_to_dict

    splits = json.loads((ROOT / "data" / "splits.json").read_text(encoding="utf-8"))
    ids = splits.get(split, [])
    if limit:
        ids = ids[:limit]

    init_db()
    llm = AnthropicClient()

    agg = {k: {"tp": 0, "fp": 0, "fn": 0} for k in (
        "supplier_name", "document_number", "issue_date", "due_date",
        "currency", "doc_kind", "subtotal", "tax_total", "total", "line_items.*",
    )}
    costs, times = [], []
    total_in = total_out = 0
    cache_read = cache_write = 0
    review_rates = []
    review_error_caught = 0
    review_wrong_total = 0
    auto_tp = auto_fp = auto_wrong = 0
    trace_ok = trace_total = 0
    n_ok = n_err = 0
    per_doc = []

    for doc_id in ids:
        label = json.loads((LABELS / f"{doc_id}.json").read_text(encoding="utf-8"))
        path = _find_file(doc_id)
        if path is None:
            continue
        results = process_document(llm, path, config=config, doc_id=doc_id, write_outputs=False)
        r = results[0]
        if r.error:
            n_err += 1
            per_doc.append({"doc_id": doc_id, "error": r.error})
            continue
        n_ok += 1
        pred = doc_to_dict(r.doc) if r.doc else None
        fields = score_doc(pred, label, config)
        for k, counters in fields.items():
            for outcome, _st in counters:
                if outcome == "tp":
                    agg[k]["tp"] += 1
                elif outcome == "fp":
                    agg[k]["fp"] += 1
                elif outcome == "fn":
                    agg[k]["fn"] += 1

        if r.metrics:
            costs.append(r.metrics.cost_usd)
            times.append(r.metrics.ms_total)
            total_in += r.metrics.input_tokens + r.metrics.cache_read_input_tokens + r.metrics.cache_creation_input_tokens
            total_out += r.metrics.output_tokens
            cache_read += r.metrics.cache_read_input_tokens
            cache_write += r.metrics.cache_creation_input_tokens

        c, t = _traceability(pred, label)
        trace_ok += c
        trace_total += t

        if config == "full" and pred is not None and r.metrics:
            fields_total = r.metrics.fields_total or 1
            nr = r.metrics.fields_needs_review
            review_rates.append(nr / fields_total)
            # review error recall: of the scalar fields that are WRONG (fp), how many are needs_review?
            for key in (
                "supplier_name", "document_number", "issue_date", "due_date",
                "currency", "doc_kind", "subtotal", "tax_total", "total",
            ):
                pf = pred.get(key)
                pv = _field_value(pf)
                lv = label.get(key)
                if pv is None:
                    continue
                wrong = False
                if lv is None:
                    wrong = True
                else:
                    matcher = {
                        "supplier_name": match_supplier, "document_number": match_doc_number,
                        "issue_date": match_date, "due_date": match_date,
                        "currency": match_currency, "doc_kind": match_bool,
                        "subtotal": match_money, "tax_total": match_money, "total": match_money,
                    }[key]
                    wrong = not matcher(pv, lv)
                if wrong:
                    review_wrong_total += 1
                    if _field_status(pf) == "needs_review":
                        review_error_caught += 1
                # auto-accepted precision
                if _field_status(pf) == "ok":
                    if wrong:
                        auto_fp += 1
                    else:
                        auto_tp += 1

        per_doc.append({
            "doc_id": doc_id,
            "doc_type": r.doc_type,
            "cost_usd": round(r.metrics.cost_usd, 6) if r.metrics else None,
            "ms_total": r.metrics.ms_total if r.metrics else None,
            "retries": r.metrics.retries if r.metrics else None,
            "fields_needs_review": r.metrics.fields_needs_review if r.metrics else None,
        })

    table = {k: prf(v["tp"], v["fp"], v["fn"]) for k, v in agg.items()}
    all_tp = sum(v["tp"] for v in agg.values())
    all_fp = sum(v["fp"] for v in agg.values())
    all_fn = sum(v["fn"] for v in agg.values())
    overall = prf(all_tp, all_fp, all_fn)

    result = {
        "config": config,
        "split": split,
        "n_docs": len(ids),
        "n_ok": n_ok,
        "n_err": n_err,
        "model": "claude-haiku-5-5",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": overall,
        "per_field": table,
        "ops": {
            "cost_per_doc_mean_usd": round(statistics.mean(costs), 6) if costs else None,
            "cost_per_doc_p95_usd": round(_p95(costs), 6) if costs else None,
            "time_per_doc_mean_s": round(statistics.mean(times) / 1000, 3) if times else None,
            "time_per_doc_p95_s": round(_p95(times) / 1000, 3) if times else None,
            "total_cost_usd": round(sum(costs), 6),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
        },
        "per_doc": per_doc,
    }
    if config == "full":
        result["review"] = {
            "review_rate_mean": round(statistics.mean(review_rates), 4) if review_rates else None,
            "auto_accepted_precision": round(auto_tp / (auto_tp + auto_fp), 4) if (auto_tp + auto_fp) else None,
            "review_error_recall": round(review_error_caught / review_wrong_total, 4) if review_wrong_total else None,
            "wrong_scalar_fields": review_wrong_total,
            "caught_by_review": review_error_caught,
        }
    result["traceability"] = {
        "page_accuracy": round(trace_ok / trace_total, 4) if trace_total else None,
        "n_fields_with_page": trace_total,
    }

    if write_report:
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / f"eval_{config}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        _write_md(result, REPORTS / "eval_report.md" if config == "full" else REPORTS / f"eval_report_{config}.md")
    return result


def _p95(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    idx = min(len(xs) - 1, int(0.95 * len(xs)))
    return xs[idx]


def _write_md(result: dict, path: Path) -> None:
    lines = []
    lines.append(f"# InvoiceLens eval — {result['config']} ({result['split']})")
    lines.append("")
    lines.append(f"- Model: `{result['model']}`")
    lines.append(f"- Timestamp: {result['timestamp']}")
    lines.append(f"- Docs: {result['n_ok']} ok / {result['n_err']} error (of {result['n_docs']})")
    lines.append("")
    lines.append("## Per-field precision / recall / F1")
    lines.append("")
    lines.append("| Field | TP | FP | FN | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|")
    for k, v in result["per_field"].items():
        lines.append(
            f"| {k} | {v['tp']} | {v['fp']} | {v['fn']} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1']:.3f} |"
        )
    a = result["aggregate"]
    lines.append(f"| **overall** | {a['tp']} | {a['fp']} | {a['fn']} | {a['precision']:.3f} | {a['recall']:.3f} | {a['f1']:.3f} |")
    lines.append("")
    lines.append("## Ops")
    o = result["ops"]
    lines.append(f"- Cost/doc mean: ${o['cost_per_doc_mean_usd']:.6f}  p95: ${o['cost_per_doc_p95_usd']:.6f}")
    lines.append(f"- Time/doc mean: {o['time_per_doc_mean_s']:.3f}s  p95: {o['time_per_doc_p95_s']:.3f}s")
    lines.append(f"- Total cost: ${o['total_cost_usd']:.6f}")
    lines.append(f"- Tokens in/out: {o['total_input_tokens']} / {o['total_output_tokens']}")
    lines.append("")
    if "review" in result:
        r = result["review"]
        lines.append("## Review routing")
        lines.append(f"- Review rate (mean fields/doc): {r['review_rate_mean']}")
        lines.append(f"- Auto-accepted precision: {r['auto_accepted_precision']}")
        lines.append(f"- Review error recall: {r['review_error_recall']} ({r['caught_by_review']}/{r['wrong_scalar_fields']} wrong fields caught)")
        lines.append("")
    tr = result["traceability"]
    lines.append("## Traceability")
    lines.append(f"- Source-page accuracy: {tr['page_accuracy']} over {tr['n_fields_with_page']} fields")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_eval()
