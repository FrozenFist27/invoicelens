"""Deterministic validation rules (IDEATION section 8).

Rule codes: schema, arith_line, arith_subtotal, arith_total, date_format,
date_order, currency_code, not_grounded, missing_required.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from rapidfuzz import fuzz

from .models import InvoiceDoc, LineItem, ValidationIssue

# Bundled ISO 4217 subset used by the synthetic dataset + common codes.
ISO4217 = {
    "USD", "EUR", "GBP", "INR", "AUD", "CAD", "JPY", "CHF", "SGD", "AED",
    "CNY", "HKD", "NZD", "SEK", "NOK", "DKK", "ZAR", "BRL", "MXN", "KRW",
}

REQUIRED_FIELDS = ("supplier_name", "document_number", "issue_date", "currency", "total")

ABS_TOL = Decimal("0.02")
LINE_TOL = Decimal("0.01")
LINE_TOL_PCT = Decimal("0.005")


def _dec(v) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def check_arith_line(item: LineItem, idx: int) -> ValidationIssue | None:
    """quantity * unit_price == amount (abs 0.01 or 0.5%)."""
    q = _dec(item.quantity.value)
    u = _dec(item.unit_price.value)
    a = _dec(item.amount.value)
    if q is None or u is None or a is None:
        return None
    expected = q * u
    diff = abs(expected - a)
    if diff <= LINE_TOL:
        return None
    if a != 0 and diff / abs(a) <= LINE_TOL_PCT:
        return None
    return ValidationIssue(
        field_path=f"line_items[{idx}].amount",
        code="arith_line",
        message=f"line {idx}: quantity {q} x unit_price {u} = {expected}, but amount = {a}",
    )


def check_arith_subtotal(doc: InvoiceDoc) -> ValidationIssue | None:
    amounts = [_dec(li.amount.value) for li in doc.line_items]
    if not amounts or any(a is None for a in amounts):
        return None
    subtotal = _dec(doc.subtotal.value)
    if subtotal is None:
        return None
    s = sum(amounts, Decimal(0))
    if abs(s - subtotal) <= ABS_TOL:
        return None
    return ValidationIssue(
        field_path="subtotal",
        code="arith_subtotal",
        message=f"sum of line amounts = {s}, but subtotal = {subtotal}",
    )


def check_arith_total(doc: InvoiceDoc) -> ValidationIssue | None:
    subtotal = _dec(doc.subtotal.value)
    tax = _dec(doc.tax_total.value)
    total = _dec(doc.total.value)
    if subtotal is None or total is None:
        return None
    if tax is None:
        # tax null: only ok if subtotal == total
        if abs(subtotal - total) <= ABS_TOL:
            return None
        return ValidationIssue(
            field_path="total",
            code="arith_total",
            message=f"tax_total is null and subtotal {subtotal} != total {total}",
        )
    if abs(subtotal + tax - total) <= ABS_TOL:
        return None
    return ValidationIssue(
        field_path="total",
        code="arith_total",
        message=f"subtotal {subtotal} + tax_total {tax} = {subtotal + tax}, but total = {total}",
    )


def check_date_format(doc: InvoiceDoc) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name in ("issue_date", "due_date"):
        f = getattr(doc, name)
        v = f.value
        if v is None:
            continue
        if not isinstance(v, date):
            issues.append(
                ValidationIssue(
                    field_path=name,
                    code="date_format",
                    message=f"{name} is not a date: {v!r}",
                )
            )
            continue
        if not (1990 <= v.year <= 2100):
            issues.append(
                ValidationIssue(
                    field_path=name,
                    code="date_format",
                    message=f"{name} year {v.year} out of range 1990..2100",
                )
            )
    return issues


def check_date_order(doc: InvoiceDoc) -> ValidationIssue | None:
    if doc.issue_date.value and doc.due_date.value:
        if doc.due_date.value < doc.issue_date.value:
            return ValidationIssue(
                field_path="due_date",
                code="date_order",
                message=f"due_date {doc.due_date.value} < issue_date {doc.issue_date.value}",
            )
    return None


def check_currency(doc: InvoiceDoc) -> ValidationIssue | None:
    c = doc.currency.value
    if c is None:
        return None
    if c.upper() not in ISO4217:
        return ValidationIssue(
            field_path="currency",
            code="currency_code",
            message=f"currency {c!r} not in ISO 4217 list",
        )
    return None


def check_missing_required(doc: InvoiceDoc) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for name in REQUIRED_FIELDS:
        f = getattr(doc, name)
        if f.value is None:
            issues.append(
                ValidationIssue(
                    field_path=name,
                    code="missing_required",
                    message=f"required field {name} is missing",
                )
            )
    return issues


def normalize_for_grounding(value) -> str:
    """Normalise a value for substring grounding: digits, letters, lowercased."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    return s


def digits_of(value) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit() or ch == ".")


def check_grounded(doc: InvoiceDoc, page_texts: dict[str, str], fuzzy_threshold: int = 85) -> list[ValidationIssue]:
    """Each non-null field's normalised value (or its digits) appears in the cited page text."""
    issues: list[ValidationIssue] = []

    def one(path: str, value, page: str | None):
        if value is None or page is None:
            return
        text = page_texts.get(page, "")
        if not text:
            return
        norm_val = normalize_for_grounding(value)
        norm_text = normalize_for_grounding(text)
        if norm_val and norm_val in norm_text:
            return
        dig = digits_of(value)
        if dig and dig in digits_of(text):
            return
        # fuzzy (for OCR pages)
        if norm_val and fuzz.partial_ratio(norm_val, norm_text) >= fuzzy_threshold:
            return
        issues.append(
            ValidationIssue(
                field_path=path,
                code="not_grounded",
                message=f"value {value!r} not found in cited page {page!r}",
            )
        )

    for name in REQUIRED_FIELDS + ("supplier_tax_id", "due_date", "subtotal", "tax_total"):
        f = getattr(doc, name, None)
        if f is None:
            continue
        if f.value is not None and f.source is not None:
            one(name, f.value, f.source.page)
    for i, li in enumerate(doc.line_items):
        for sub in ("description", "quantity", "unit_price", "amount"):
            f = getattr(li, sub)
            if f.value is not None and f.source is not None:
                one(f"line_items[{i}].{sub}", f.value, f.source.page)
    return issues


def validate_doc(
    doc: InvoiceDoc,
    page_texts: dict[str, str] | None = None,
    fuzzy_threshold: int = 85,
) -> list[ValidationIssue]:
    """Run all rules; return the list of issues (empty = valid)."""
    issues: list[ValidationIssue] = []
    issues.extend(check_missing_required(doc))
    issues.extend(check_date_format(doc))
    o = check_date_order(doc)
    if o:
        issues.append(o)
    c = check_currency(doc)
    if c:
        issues.append(c)
    st = check_arith_subtotal(doc)
    if st:
        issues.append(st)
    t = check_arith_total(doc)
    if t:
        issues.append(t)
    for i, li in enumerate(doc.line_items):
        li_issue = check_arith_line(li, i)
        if li_issue:
            issues.append(li_issue)
    if page_texts:
        issues.extend(check_grounded(doc, page_texts, fuzzy_threshold))
    return issues


def fields_with_issues(issues: list[ValidationIssue]) -> set[str]:
    """Set of field paths touched by any issue."""
    return {i.field_path for i in issues}
