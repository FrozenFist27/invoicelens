# InvoiceLens eval — full (dev)

- Model: `claude-haiku-5-5`  |  commit: `56427c4`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T17:12:49.035610+00:00
- Docs: 40 ok / 0 error (of 40)

## Per-field precision / recall / F1

| Field | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| supplier_name | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| document_number | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| issue_date | 39 | 1 | 1 | 0.975 | 0.975 | 0.975 |
| due_date | 30 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| currency | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| doc_kind | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| subtotal | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| tax_total | 28 | 2 | 1 | 0.933 | 0.966 | 0.949 |
| total | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| line_items.* | 814 | 2 | 6 | 0.998 | 0.993 | 0.995 |
| **overall** | 1151 | 5 | 8 | 0.996 | 0.993 | 0.994 |

## Ops
- Cost/doc mean: $0.001055  p95: $0.001695
- Time/doc mean: 9.140s  p95: 27.606s
- Total cost: $0.042189
- Tokens in/out: 243849 / 72709

## Review routing
- Review rate (mean fields/doc): 0.027
- Auto-accepted precision: 1.0
- Review error recall: 1.0 (3/3 wrong fields caught)

## Threshold sensitivity (scalar fields, confidence-only)

| Threshold | Review rate | Auto-accepted precision |
|---|---|---|
| 0.5 | 0.0059 | 0.9911 |
| 0.6 | 0.0059 | 0.9911 |
| 0.7 | 0.0353 | 0.9939 |
| 0.8 | 0.0706 | 1.0 |

## Traceability
- Source-page accuracy: 0.9971 over 340 fields