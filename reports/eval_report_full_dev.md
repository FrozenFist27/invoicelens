# InvoiceLens eval — full (dev)

- Model: `claude-haiku-5-5`  |  commit: `941dbe7`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T17:01:51.021825+00:00
- Docs: 40 ok / 0 error (of 40)

## Per-field precision / recall / F1

| Field | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| supplier_name | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| document_number | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| issue_date | 38 | 2 | 2 | 0.950 | 0.950 | 0.950 |
| due_date | 29 | 1 | 1 | 0.967 | 0.967 | 0.967 |
| currency | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| doc_kind | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| subtotal | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| tax_total | 28 | 1 | 1 | 0.966 | 0.966 | 0.966 |
| total | 39 | 1 | 1 | 0.975 | 0.975 | 0.975 |
| line_items.* | 813 | 2 | 7 | 0.998 | 0.992 | 0.995 |
| **overall** | 1147 | 7 | 12 | 0.994 | 0.990 | 0.992 |

## Ops
- Cost/doc mean: $0.001159  p95: $0.002375
- Time/doc mean: 9.491s  p95: 26.018s
- Total cost: $0.046375
- Tokens in/out: 270374 / 79236

## Review routing
- Review rate (mean fields/doc): 0.0452
- Auto-accepted precision: 0.988
- Review error recall: 0.2 (1/5 wrong fields caught)

## Threshold sensitivity (scalar fields, confidence-only)

| Threshold | Review rate | Auto-accepted precision |
|---|---|---|
| 0.5 | 0.0088 | 0.9881 |
| 0.6 | 0.0177 | 0.988 |
| 0.7 | 0.0177 | 0.988 |
| 0.8 | 0.0206 | 0.988 |

## Traceability
- Source-page accuracy: 1.0 over 339 fields