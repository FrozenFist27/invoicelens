# Project Catalog offer (draft)

Status: draft for the human to review. Prices are deliberately left blank: the owner decides them.

**Title:** I will build an invoice / PO data extraction pipeline with measured accuracy

**One-line pitch:** Invoices and purchase orders in (text PDF, scanned PDF, spreadsheet, email), validated JSON and CSV out, with every field traced to its source page and accuracy measured on documents you share.

| Tier | Scope | Delivery | Price (human decides) |
|---|---|---|---|
| Starter | 1 document type (for example text PDF invoices), fixed schema, JSON/CSV output, accuracy report on up to 20 of your sample documents | 5 days | $[decide] |
| Standard | Up to 3 input types including scanned PDFs, validation plus retry, review queue, accuracy report on up to 50 documents | 10 days | $[decide] |
| Advanced | All 4 input types including email, custom fields, simple web upload/review UI, deployment to your cloud, handover docs | 15 days | $[decide] |

**What the buyer gets**
- Python package and CLI, with tests.
- Fixed output schema (supplier, document number, dates, currency, line items, totals) with a source page or cell reference on every value.
- Deterministic checks (line arithmetic, subtotal and total, date order, currency codes) with targeted correction retries.
- Review queue for fields the system is unsure about, instead of silent guesses.
- Accuracy report: per-field precision and recall, cost per document, time per document.

**Requirements from the buyer**
- 20 to 50 sample documents they are allowed to share (redacted is fine).
- Target field list and the destination for the output (CSV, database, ERP import file).
- An LLM API key with a spend cap (the buyer pays their own usage; see the measured cost per document in the README).

**Not included**
- Handwriting recognition, multi-invoice PDFs, non-English documents (can be quoted as add-ons).
- Direct ERP or accounting integrations (add-on).

**Honest framing for the listing:** the public demo runs on synthetic data. Real-world accuracy depends on your documents, which is why every tier starts with a measurement on your own samples.
