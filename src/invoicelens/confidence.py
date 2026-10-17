"""Confidence scoring (IDEATION section 9).

score = 0.5 * llm_confidence + 0.3 * grounding + 0.2 * rule_pass
OCR pages: score *= min(1, ocr_mean_conf/90)
Required + null value -> 0
"""

from __future__ import annotations

from rapidfuzz import fuzz

from .models import DocumentText, Field, InvoiceDoc
from .settings import get_settings
from .validate import normalize_for_grounding, fields_with_issues


def grounding_score(value, page_text: str, ocr: bool, fuzzy_threshold: int = 85) -> float:
    if value is None or not page_text:
        return 0.0
    norm_val = normalize_for_grounding(value)
    norm_text = normalize_for_grounding(page_text)
    if norm_val and norm_val in norm_text:
        return 1.0
    dig = "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")
    if dig and dig in "".join(ch for ch in norm_text if ch.isdigit() or ch == "."):
        return 1.0
    if norm_val and fuzz.partial_ratio(norm_val, norm_text) >= fuzzy_threshold:
        return 0.6
    return 0.0


def _score_field(
    f: Field,
    page_texts: dict[str, str],
    issue_paths: set[str],
    path: str,
    required: bool,
    ocr_conf: dict[str, float | None],
    cfg,
) -> None:
    if f.value is None and required:
        f.confidence = 0.0
        return
    if f.value is None:
        f.confidence = 0.0
        return
    page = f.source.page if f.source else None
    text = page_texts.get(page, "") if page else ""
    is_ocr = bool(page and ocr_conf.get(page) is not None)
    g = grounding_score(f.value, text, is_ocr, cfg.grounding.fuzzy_threshold)
    rule_pass = 0.0 if path in issue_paths else 1.0
    score = (
        cfg.confidence_weights.llm * f.llm_confidence
        + cfg.confidence_weights.grounding * g
        + cfg.confidence_weights.rules * rule_pass
    )
    if page and ocr_conf.get(page) is not None:
        score *= min(1.0, (ocr_conf[page] or 0) / 90.0)
    f.confidence = max(0.0, min(1.0, score))


def score_doc(doc: InvoiceDoc, doc_text: DocumentText, issues: list) -> None:
    """Assign final confidence and ok/needs_review status to every field."""
    cfg = get_settings()
    page_texts = {p.ref: p.text for p in doc_text.pages}
    ocr_conf = {p.ref: p.ocr_confidence for p in doc_text.pages}
    issue_paths = fields_with_issues(issues)
    threshold = cfg.review_threshold

    _score_field(doc.doc_kind, page_texts, issue_paths, "doc_kind", True, ocr_conf, cfg)
    _score_field(doc.supplier_name, page_texts, issue_paths, "supplier_name", True, ocr_conf, cfg)
    _score_field(doc.supplier_tax_id, page_texts, issue_paths, "supplier_tax_id", False, ocr_conf, cfg)
    _score_field(doc.document_number, page_texts, issue_paths, "document_number", True, ocr_conf, cfg)
    _score_field(doc.issue_date, page_texts, issue_paths, "issue_date", True, ocr_conf, cfg)
    _score_field(doc.due_date, page_texts, issue_paths, "due_date", False, ocr_conf, cfg)
    _score_field(doc.currency, page_texts, issue_paths, "currency", True, ocr_conf, cfg)
    _score_field(doc.subtotal, page_texts, issue_paths, "subtotal", False, ocr_conf, cfg)
    _score_field(doc.tax_total, page_texts, issue_paths, "tax_total", False, ocr_conf, cfg)
    _score_field(doc.total, page_texts, issue_paths, "total", True, ocr_conf, cfg)
    for i, li in enumerate(doc.line_items):
        for sub in ("description", "quantity", "unit_price", "amount"):
            _score_field(
                getattr(li, sub), page_texts, issue_paths, f"line_items[{i}].{sub}", False, ocr_conf, cfg
            )

    # status: needs_review if below threshold OR the field path has an issue.
    # Absent optional fields (value None, not required) stay ok — nothing to review.
    _REQUIRED = {"doc_kind", "supplier_name", "document_number", "issue_date", "currency", "total"}
    for name in (
        "doc_kind", "supplier_name", "supplier_tax_id", "document_number",
        "issue_date", "due_date", "currency", "subtotal", "tax_total", "total",
    ):
        f = getattr(doc, name)
        if f.value is None and name not in _REQUIRED:
            f.status = "ok"
        else:
            f.status = "needs_review" if (f.confidence < threshold or name in issue_paths) else "ok"
    for i, li in enumerate(doc.line_items):
        for sub in ("description", "quantity", "unit_price", "amount"):
            f = getattr(li, sub)
            path = f"line_items[{i}].{sub}"
            if f.value is None:
                f.status = "ok"
            else:
                f.status = "needs_review" if (f.confidence < threshold or path in issue_paths) else "ok"


def iter_fields(doc: InvoiceDoc):
    """Yield (field_path, Field) for every field in the doc."""
    for name in (
        "doc_kind", "supplier_name", "supplier_tax_id", "document_number",
        "issue_date", "due_date", "currency", "subtotal", "tax_total", "total",
    ):
        yield name, getattr(doc, name)
    for i, li in enumerate(doc.line_items):
        for sub in ("description", "quantity", "unit_price", "amount"):
            yield f"line_items[{i}].{sub}", getattr(li, sub)
