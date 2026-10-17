# Upwork portfolio entry (draft)

**Title:** InvoiceLens - Invoice & PO Extraction with Measured Accuracy (Demo Project)

**Label to keep visible in the entry:** *Demo project built on synthetic data. No client data.*

**Role:** Solo developer (design, build, evaluation)

**Description**

Demo project built on synthetic data. A Python pipeline that turns supplier invoices and purchase orders (text PDFs, scanned PDFs, spreadsheets and email bodies) into validated JSON and CSV. An LLM (Claude Haiku) extracts a fixed schema; deterministic rules check line-item arithmetic, totals, dates and currency codes; failures trigger a targeted correction retry; uncertain fields go to a review queue instead of being guessed. Every field links back to its source page or cell.

Measured results (synthetic documents, run on 2026-10-17):
- 10 held-out documents: field F1 0.995 for both a plain single call and the full pipeline (the model is already accurate on clean synthetic documents).
- 40 development documents: F1 0.984 baseline vs 0.994 with validation and retries; every wrong scalar field (3 of 3) was routed to review, none was auto-accepted.
- About $0.001 per document in LLM cost; about 6 seconds per digital document and 19 seconds per scanned document.
- 74 automated tests, no network needed.

Honest limits: synthetic data, small held-out set (n=10), single run per configuration. Real-world accuracy depends on your documents, so I start every engagement by measuring on your own samples.

**Skills:** Python, LLM / Claude API, OCR (Tesseract), PDF processing, Data Extraction, FastAPI, Pydantic, Automated Testing.

**Links to add when available:** GitHub repo (not yet published), live demo (Hugging Face Space, not yet deployed), 2-minute video (script in `docs/VIDEO_SCRIPT.md`).

See also `docs/PROJECT_CATALOG.md` for the Project Catalog tiers (prices left for the owner to set).
