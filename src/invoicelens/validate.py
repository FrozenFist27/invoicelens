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
        related=[f"line_items[{idx}].quantity", f"line_items[{idx}].unit_price"],
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
        related=[f"line_items[{i}].amount" for i in range(len(doc.line_items))],
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
            related=["subtotal", "tax_total"],
            code="arith_total",
            message=f"tax_total is null and subtotal {subtotal} != total {total}",
        )
    if abs(subtotal + tax - total) <= ABS_TOL:
        return None
    return ValidationIssue(
        field_path="total",
        related=["subtotal", "tax_total"],
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
    """Digits only (separators dropped), so 1.234,56 / 1,234.56 / 1234.56 all compare equal."""
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def number_tokens(text: str) -> set[Decimal]:
    """All numeric tokens in text, parsed with US or European separators."""
    import re

    vals: set[Decimal] = set()
    pattern = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?(?!\d)|\d+(?:[.,]\d+)*"
    for tok in re.findall(pattern, text):
        tok = tok.strip()
        cands = []
        t = tok
        if "," in t and "." in t:
            if t.rfind(",") > t.rfind("."):
                cands.append(t.replace(".", "").replace(",", "."))
            else:
                cands.append(t.replace(",", ""))
        elif "," in t:
            cands.append(t.replace(",", ""))
            if len(t.split(",")[-1]) <= 2:
                cands.append(t.replace(",", "."))
        else:
            cands.append(t)
        for c in cands:
            try:
                vals.add(Decimal(c))
            except InvalidOperation:
                pass
    return vals


def date_variants(d) -> set[str]:
    """Textual renderings of a date as they commonly appear in documents (lowercased)."""
    out = {
        d.isoformat(),
        d.strftime("%d/%m/%Y"), d.strftime("%m/%d/%Y"),
        d.strftime("%d-%m-%Y"), d.strftime("%m-%d-%Y"),
        d.strftime("%d.%m.%Y"), d.strftime("%Y/%m/%d"),
    }
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d-%b-%Y"):
        out.add(d.strftime(fmt).lower())
        out.add(d.strftime(fmt).lower().lstrip("0"))
        out.add(d.strftime(fmt).lower().replace(" 0", " "))
    out.add(f"{d.day}/{d.month}/{d.year}")
    out.add(f"{d.month}/{d.day}/{d.year}")
    return {v.lower() for v in out}


def _show(value) -> str:
    return value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, Decimal) else repr(value)


def resolve_page(page: str | None, page_texts: dict[str, str]) -> str | None:
    """Map a cited page ref (p1, Sheet!B7, body) to a key of page_texts, if possible."""
    if not page or not page_texts:
        return None
    if page in page_texts:
        return page
    head = page.split("!", 1)[0]
    if head in page_texts:
        return head
    if len(page_texts) == 1:  # single-page doc: any citation points at it
        return next(iter(page_texts))
    return None


def grounding_match(value, text: str, fuzzy_threshold: int = 85) -> str | None:
    """'exact' if the value (in any common rendering) is in text, 'fuzzy' if close, else None."""
    if value is None or not text:
        return None
    norm_val = normalize_for_grounding(value)
    norm_text = normalize_for_grounding(text)
    numeric = isinstance(value, (Decimal, int, float))
    if isinstance(value, date):
        if any(v in norm_text for v in date_variants(value)):
            return "exact"
    elif numeric:
        if Decimal(str(value)) in number_tokens(text):
            return "exact"
    else:
        if norm_val and norm_val in norm_text:
            return "exact"
        dig = digits_of(value)
        if dig and len(dig) >= 3 and dig in digits_of(text):
            return "exact"
    if norm_val and not isinstance(value, date) and not numeric:
        if fuzz.partial_ratio(norm_val, norm_text) >= fuzzy_threshold:
            return "fuzzy"
    return None


def check_grounded(doc: InvoiceDoc, page_texts: dict[str, str], fuzzy_threshold: int = 85) -> list[ValidationIssue]:
    """Each non-null field's value (in any common rendering) appears in the cited page text."""
    issues: list[ValidationIssue] = []

    def one(path: str, value, page: str | None):
        if value is None or page is None:
            return
        key = resolve_page(page, page_texts)
        if key is None:
            issues.append(
                ValidationIssue(
                    field_path=path,
                    code="not_grounded",
                    message=f"cited page {page!r} does not exist in the document",
                )
            )
            return
        if grounding_match(value, page_texts[key], fuzzy_threshold) is None:
            issues.append(
                ValidationIssue(
                    field_path=path,
                    code="not_grounded",
                    message=f"value {_show(value)} not found in cited page {page!r}",
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


_NUMERIC_DATE = None


def check_date_ambiguity(doc: InvoiceDoc, page_texts: dict[str, str]) -> list[ValidationIssue]:
    """Detect dd/mm vs mm/dd confusion on numeric dates.

    The ordering is resolved from any numeric date in the document whose first part is > 12
    (day first) or whose second part is > 12 (month first). If the extracted date contradicts the
    resolved ordering the issue is retriable (date_format); if the ordering cannot be resolved the
    issue is `date_ambiguous` (not retriable, goes straight to review).
    """
    import re

    global _NUMERIC_DATE
    if _NUMERIC_DATE is None:
        _NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?!\d)")
    if not page_texts:
        return []
    tokens = [(int(a), int(b), int(y)) for t in page_texts.values() for a, b, y in _NUMERIC_DATE.findall(t)]
    style = None
    if any(a > 12 for a, _, _ in tokens):
        style = "dmy"
    elif any(b > 12 for _, b, _ in tokens):
        style = "mdy"
    issues: list[ValidationIssue] = []
    for name in ("issue_date", "due_date"):
        d = getattr(doc, name).value
        if not isinstance(d, date) or d.day == d.month:
            continue
        pair = {d.day, d.month}
        match = [(a, b) for a, b, y in tokens if y == d.year and {a, b} == pair]
        if not match:
            continue  # not printed in numeric form (or not found): nothing to resolve
        if style is None:
            issues.append(
                ValidationIssue(
                    field_path=name,
                    code="date_ambiguous",
                    message=f"{name} is printed as {match[0][0]:02d}/{match[0][1]:02d}/{d.year}; "
                    "day/month order cannot be determined from the document",
                )
            )
            continue
        a, b = match[0]
        expected = (a, b) if style == "dmy" else (b, a)  # (day, month)
        if (d.day, d.month) != expected:
            issues.append(
                ValidationIssue(
                    field_path=name,
                    code="date_format",
                    message=f"the document uses {'day/month/year' if style == 'dmy' else 'month/day/year'} "
                    f"order (another date proves it); {a:02d}/{b:02d}/{d.year} means "
                    f"{d.year}-{expected[1]:02d}-{expected[0]:02d}, not {d.isoformat()}",
                )
            )
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
        issues.extend(check_date_ambiguity(doc, page_texts))
    return issues


def fields_with_issues(issues: list[ValidationIssue]) -> set[str]:
    """Set of field paths touched by any issue (the failing field plus fields implicated with it)."""
    out: set[str] = set()
    for i in issues:
        out.add(i.field_path)
        out.update(getattr(i, "related", []))
    return out
