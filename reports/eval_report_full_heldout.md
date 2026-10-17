# InvoiceLens eval — full (heldout)

- Model: `claude-haiku-5-5`  |  commit: `941dbe7`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T16:55:13.533298+00:00
- Docs: 10 ok / 0 error (of 10)

## Per-field precision / recall / F1

| Field | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| supplier_name | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| document_number | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| issue_date | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| due_date | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| currency | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| doc_kind | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| subtotal | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| tax_total | 8 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| total | 9 | 1 | 1 | 0.900 | 0.900 | 0.900 |
| line_items.* | 217 | 0 | 3 | 1.000 | 0.986 | 0.993 |
| **overall** | 304 | 1 | 4 | 0.997 | 0.987 | 0.992 |

## Ops
- Cost/doc mean: $0.001032  p95: $0.001329
- Time/doc mean: 8.297s  p95: 13.421s
- Total cost: $0.010317
- Tokens in/out: 61382 / 18122

## Review routing
- Review rate (mean fields/doc): 0.0053
- Auto-accepted precision: 1.0
- Review error recall: 1.0 (1/1 wrong fields caught)

## Threshold sensitivity (scalar fields, confidence-only)

| Threshold | Review rate | Auto-accepted precision |
|---|---|---|
| 0.5 | 0.0114 | 1.0 |
| 0.6 | 0.0114 | 1.0 |
| 0.7 | 0.0114 | 1.0 |
| 0.8 | 0.0227 | 1.0 |

## Traceability
- Source-page accuracy: 1.0 over 88 fields