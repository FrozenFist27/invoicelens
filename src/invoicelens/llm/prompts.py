"""Prompt templates + the flattened record_invoice tool schema.

Write fresh; no reuse from any client (IDEATION section 7).
"""

from __future__ import annotations

TOOL_NAME = "record_invoice"

# Flattened field shape: every field is {value, page, snippet, confidence}.
_FIELD = {
    "type": ["object", "null"],
    "properties": {
        "value": {
            "type": ["string", "number", "null"],
            "description": "The extracted value, or null if absent.",
        },
        "page": {
            "type": ["string", "null"],
            "description": "Page marker exactly as it appears in the bracket heading the text: 'p1', 'p2', 'body', or for spreadsheets the sheet name plus cell, e.g. 'Invoice!D10'.",
        },
        "snippet": {
            "type": ["string", "null"],
            "description": "Verbatim supporting text from the source, <=200 chars.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Self-reported confidence 0..1. 0.9+ only if read verbatim and unambiguous.",
        },
    },
    "required": ["value", "page", "snippet", "confidence"],
    "additionalProperties": False,
}


def _line_item() -> dict:
    return {
        "type": "object",
        "properties": {
            "description": _FIELD,
            "quantity": _FIELD,
            "unit_price": _FIELD,
            "amount": _FIELD,
        },
        "required": ["description", "quantity", "unit_price", "amount"],
        "additionalProperties": False,
    }


INVOICE_TOOL: dict = {
    "name": TOOL_NAME,
    "description": (
        "Record the extracted invoice or purchase-order fields. "
        "Every field carries value, page, snippet and confidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_kind": {
                **_FIELD,
                "properties": {
                    **_FIELD["properties"],
                    "value": {
                        "type": ["string", "null"],
                        "enum": ["invoice", "purchase_order", None],
                    },
                },
            },
            "supplier_name": _FIELD,
            "supplier_tax_id": _FIELD,
            "document_number": _FIELD,
            "issue_date": {
                **_FIELD,
                "properties": {
                    **_FIELD["properties"],
                    "value": {
                        "type": ["string", "null"],
                        "description": "ISO date YYYY-MM-DD or null.",
                    },
                },
            },
            "due_date": {
                **_FIELD,
                "properties": {
                    **_FIELD["properties"],
                    "value": {
                        "type": ["string", "null"],
                        "description": "ISO date YYYY-MM-DD or null.",
                    },
                },
            },
            "currency": {
                **_FIELD,
                "properties": {
                    **_FIELD["properties"],
                    "value": {
                        "type": ["string", "null"],
                        "description": "ISO 4217 3-letter code, e.g. USD.",
                    },
                },
            },
            "line_items": {
                "type": "array",
                "items": _line_item(),
                "description": "One entry per line item.",
            },
            "subtotal": _FIELD,
            "tax_total": _FIELD,
            "total": _FIELD,
        },
        "required": [
            "doc_kind", "supplier_name", "supplier_tax_id", "document_number",
            "issue_date", "due_date", "currency", "line_items", "subtotal", "tax_total", "total",
        ],
        "additionalProperties": False,
    },
}

CORRECTION_TOOL: dict = {
    "name": "record_correction",
    "description": "Record corrected values for only the fields listed in fields_to_update.",
    "input_schema": {
        "type": "object",
        "properties": {
            "fields_to_update": {
                "type": "array",
                "description": "Only the fields that failed validation, in the same flattened shape.",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_path": {
                            "type": "string",
                            "description": "Dotted path of the field, e.g. 'total' or 'line_items[2].amount'.",
                        },
                        "value": {"type": ["string", "number", "null"]},
                        "page": {"type": ["string", "null"]},
                        "snippet": {"type": ["string", "null"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["field_path", "value", "page", "snippet", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["fields_to_update"],
        "additionalProperties": False,
    },
}

EXTRACT_SYSTEM = """You are a careful accounts-payable data entry assistant.

You extract supplier invoice and purchase-order data from a document into a fixed schema.
Rules:
- Extract only what is present in the document. Never invent a value.
- If a field is absent, set value to null and confidence to 0.
- Dates as YYYY-MM-DD.
- Currency as an ISO 4217 three-letter code. Map symbols: $ -> USD only if there is no other evidence, and lower the confidence in that case.
- Numbers: no thousands separators, dot as decimal separator.
- For every field return `page` exactly as the bracket marker that precedes the text (e.g. 'p1', 'p2', 'body'). For spreadsheets the marker is the sheet name shown in brackets: cite it with the cell, e.g. 'Invoice!D10' (never 'body') and a verbatim `snippet` from the source.
- Confidence: 0.9+ only if the value is read verbatim and unambiguous. Use 0.5-0.8 when the value is inferred or the scan is noisy. Use 0 for absent.
- doc_kind is 'invoice' or 'purchase_order'.
You must call the record_invoice tool exactly once with your extraction.
"""

EXTRACT_USER = """Document type: {doc_type}
---
{marked_text}
"""

CORRECTION_SYSTEM = EXTRACT_SYSTEM + """
On a correction request you will be told which fields failed validation.
Re-read the source text. Fix ONLY the listed fields. If the document itself is
internally inconsistent, keep the value that appears in the source, set confidence
below 0.5, and do not force the arithmetic. Call record_correction exactly once.
"""

CORRECTION_USER = """Your previous extraction failed these checks:
{issues}

Previous values for the affected fields:
{previous_fields}

Source text (same document):
---
{marked_text}

Call record_correction with corrected values for ONLY the listed fields.
"""
