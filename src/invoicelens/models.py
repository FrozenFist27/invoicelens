"""Pydantic v2 data models for InvoiceLens (IDEATION section 6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SourceRef(BaseModel):
    page: str  # "p1", "Sheet1!B7", "body"
    snippet: str | None = None  # verbatim supporting text (<=200 chars)


class Field(BaseModel, Generic[T]):
    """A value with provenance + confidence. Generic over the value type."""

    value: T | None = None
    source: SourceRef | None = None
    llm_confidence: float = 0.0  # 0..1, self-reported by the model
    confidence: float = 0.0  # final score (confidence.py)
    status: Literal["ok", "needs_review"] = "ok"


class LineItem(BaseModel):
    description: Field[str]
    quantity: Field[Decimal]
    unit_price: Field[Decimal]
    amount: Field[Decimal]


class InvoiceDoc(BaseModel):
    doc_id: str
    doc_kind: Field[Literal["invoice", "purchase_order"]]
    supplier_name: Field[str]
    supplier_tax_id: Field[str | None]
    document_number: Field[str]
    issue_date: Field[date]
    due_date: Field[date | None]
    currency: Field[str]
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Field[Decimal | None]
    tax_total: Field[Decimal | None]
    total: Field[Decimal | None]


class ValidationIssue(BaseModel):
    field_path: str  # e.g. "total", "line_items[2].amount"
    code: Literal[
        "schema",
        "arith_line",
        "arith_subtotal",
        "arith_total",
        "date_format",
        "date_order",
        "currency_code",
        "not_grounded",
        "missing_required",
    ]
    message: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class LLMCallResult(BaseModel):
    """Result of one LLM tool-use call."""

    data: dict[str, Any]  # raw tool input dict (flattened invoice)
    usage: Usage
    cost_usd: float = 0.0
    retries: int = 0


class RunMetrics(BaseModel):
    doc_id: str
    doc_type: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float = 0.0
    ms_ingest: int = 0
    ms_llm: int = 0
    ms_validate: int = 0
    ms_total: int = 0
    retries: int = 0
    fields_total: int = 0
    fields_needs_review: int = 0


class ReviewItem(BaseModel):
    id: int | None = None
    doc_id: str
    field_path: str
    suggested_value: str | None = None
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    source_page: str | None = None
    snippet: str | None = None
    status: Literal["pending", "accepted", "corrected"] = "pending"
    corrected_value: str | None = None
    created_at: datetime | None = None


class Page(BaseModel):
    ref: str  # "p1", "Sheet1!A1", "body"
    text: str
    ocr_confidence: float | None = None  # Tesseract mean word confidence, if OCR


class DocumentText(BaseModel):
    doc_id: str
    doc_type: str  # text_pdf | scanned_pdf | spreadsheet | email
    pages: list[Page] = Field(default_factory=list)
    source_path: str = ""


class PipelineResult(BaseModel):
    doc_id: str
    doc_type: str
    doc: InvoiceDoc | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    metrics: RunMetrics | None = None
    error: str | None = None
