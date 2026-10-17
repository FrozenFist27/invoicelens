# InvoiceLens eval — baseline (dev)

- Model: `claude-haiku-5-5`  |  commit: `941dbe7`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T17:01:14.011809+00:00
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
| tax_total | 28 | 1 | 1 | 0.966 | 0.966 | 0.966 |
| total | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| line_items.* | 812 | 2 | 8 | 0.998 | 0.990 | 0.994 |
| **overall** | 1149 | 4 | 10 | 0.997 | 0.991 | 0.994 |

## Ops
- Cost/doc mean: $0.000983  p95: $0.001409
- Time/doc mean: 8.556s  p95: 24.316s
- Total cost: $0.039309
- Tokens in/out: 219155 / 70837

## Traceability
- Source-page accuracy: 1.0 over 339 fields