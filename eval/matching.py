"""Field matching + normalisers (IDEATION section 11)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz


def normalize_string(s) -> str:
    if s is None:
        return ""
    s = str(s).casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_doc_number(s) -> str:
    if s is None:
        return ""
    return re.sub(r"[\s#]", "", str(s)).upper()


def to_dec(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def match_supplier(pred, label) -> bool:
    if pred is None or label is None:
        return pred is None and label is None
    return fuzz.ratio(normalize_string(pred), normalize_string(label)) >= 90


def match_doc_number(pred, label) -> bool:
    if pred is None or label is None:
        return pred is None and label is None
    return norm_doc_number(pred) == norm_doc_number(label)


def match_date(pred, label) -> bool:
    if pred is None or label is None:
        return pred is None and label is None
    return str(pred) == str(label)


def match_money(pred, label) -> bool:
    p = to_dec(pred)
    l = to_dec(label)
    if p is None or l is None:
        return p is None and l is None
    return abs(p - l) <= Decimal("0.01")


def match_currency(pred, label) -> bool:
    if pred is None or label is None:
        return pred is None and label is None
    return str(pred).upper() == str(label).upper()


def match_bool(pred, label) -> bool:
    # doc_kind
    if pred is None or label is None:
        return pred is None and label is None
    return str(pred).replace(" ", "_").lower() == str(label).replace(" ", "_").lower()


def desc_similarity(a, b) -> float:
    return fuzz.ratio(normalize_string(a), normalize_string(b)) / 100.0


def match_line_items(pred_items: list[dict], label_items: list[dict]) -> dict:
    """Greedy assignment on description similarity, then score each sub-field.

    Returns dict with tp/fp/fn counts for the sub-fields combined, and matched pairs.
    """
    pred_items = pred_items or []
    label_items = label_items or []
    # candidate pairs sorted by description similarity
    pairs = []
    for i, p in enumerate(pred_items):
        for j, l in enumerate(label_items):
            sim = desc_similarity(p.get("description", {}).get("value") if isinstance(p.get("description"), dict) else p.get("description"),
                                  l.get("description", {}).get("value") if isinstance(l.get("description"), dict) else l.get("description"))
            pairs.append((sim, i, j))
    pairs.sort(reverse=True)
    used_p, used_l = set(), set()
    matched = []
    for sim, i, j in pairs:
        if i in used_p or j in used_l:
            continue
        if sim < 0.3:
            continue
        matched.append((i, j, sim))
        used_p.add(i)
        used_l.add(j)

    def pval(item, key):
        v = item.get(key)
        if isinstance(v, dict):
            return v.get("value")
        return v

    def lval(item, key):
        return item.get(key)

    tp = fp = fn = 0
    sub = {}
    for key, matcher in (
        ("description", lambda a, b: match_supplier(a, b) if a and b else (a is None and b is None)),
        ("quantity", lambda a, b: str(a) == str(b) if a is not None and b is not None else (a is None and b is None)),
        ("unit_price", match_money),
        ("amount", match_money),
    ):
        k_tp = k_fp = k_fn = 0
        for i, j, _ in matched:
            pv = pval(pred_items[i], key)
            lv = lval(label_items[j], key)
            ok = matcher(pv, lv)
            if ok:
                k_tp += 1
            else:
                if pv is not None:
                    k_fp += 1
                if lv is not None:
                    k_fn += 1
        # unmatched predicted items -> FP for each non-null subfield
        for i, p in enumerate(pred_items):
            if i in used_p:
                continue
            for key2 in ("description", "quantity", "unit_price", "amount"):
                if pval(p, key2) is not None:
                    pass
        # count unmatched preds and labels for each subfield
        for i, p in enumerate(pred_items):
            if i in used_p:
                continue
            if pval(p, key) is not None:
                k_fp += 1
        for j, l in enumerate(label_items):
            if j in used_l:
                continue
            if lval(l, key) is not None:
                k_fn += 1
        sub[key] = {"tp": k_tp, "fp": k_fp, "fn": k_fn}
        tp += k_tp
        fp += k_fp
        fn += k_fn

    return {"tp": tp, "fp": fp, "fn": fn, "sub": sub, "matched": len(matched)}


def prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
