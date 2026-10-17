# InvoiceLens eval — baseline (heldout)

- Model: `claude-haiku-5-5`  |  commit: `941dbe7`  |  dataset: `c39e15849db64f63`
- Timestamp: 2026-10-17T16:53:41.021646+00:00
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
| line_items.* | 217 | 0 | 3 | 1.000 | 0.986 | 0.993 |
| **overall** | 305 | 0 | 3 | 1.000 | 0.990 | 0.995 |

## Ops
- Cost/doc mean: $0.000973  p95: $0.001158
- Time/doc mean: 12.066s  p95: 31.532s
- Total cost: $0.009728
- Tokens in/out: 54733 / 17523

## Traceability
- Source-page accuracy: 1.0 over 88 fields