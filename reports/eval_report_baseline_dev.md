# InvoiceLens eval — baseline (dev)

- Model: `claude-haiku-5-5`  |  commit: `56427c4`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T17:12:28.352120+00:00
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
| total | 40 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| line_items.* | 794 | 2 | 26 | 0.998 | 0.968 | 0.983 |
| **overall** | 1129 | 6 | 30 | 0.995 | 0.974 | 0.984 |

## Ops
- Cost/doc mean: $0.000994  p95: $0.001426
- Time/doc mean: 8.618s  p95: 26.674s
- Total cost: $0.039755
- Tokens in/out: 219155 / 70577

## Traceability
- Source-page accuracy: 1.0 over 339 fields