# InvoiceLens eval — full (heldout)

- Model: `claude-haiku-5-5`  |  commit: `d8660e4`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T16:50:04.343577+00:00
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
| total | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| line_items.* | 219 | 0 | 1 | 1.000 | 0.996 | 0.998 |
| **overall** | 307 | 0 | 1 | 1.000 | 0.997 | 0.998 |

## Ops
- Cost/doc mean: $0.001734  p95: $0.003128
- Time/doc mean: 13.956s  p95: 31.964s
- Total cost: $0.017336
- Tokens in/out: 92194 / 27260

## Review routing
- Review rate (mean fields/doc): 0.2574
- Auto-accepted precision: 1.0
- Review error recall: None (0/0 wrong fields caught)

## Threshold sensitivity (scalar fields, confidence-only)

| Threshold | Review rate | Auto-accepted precision |
|---|---|---|
| 0.5 | 0.0 | 1.0 |
| 0.6 | 0.0 | 1.0 |
| 0.7 | 0.0 | 1.0 |
| 0.8 | 0.0227 | 1.0 |

## Traceability
- Source-page accuracy: 1.0 over 88 fields