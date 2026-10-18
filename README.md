# InvoiceLens

*Invoices and POs in, validated JSON out, with every field traced to its source page and accuracy you can measure.*

![license](https://img.shields.io/badge/license-MIT-blue) ![tests](https://img.shields.io/badge/tests-74%20passing-brightgreen)

> Built and measured on 50 synthetic, fictional documents. Real-world accuracy will differ; see [Limitations](#limitations).

## Problem

Accounts-payable teams receive supplier invoices and purchase orders as text PDFs, scanned PDFs, spreadsheets and email bodies, and retype them into an ERP. Generic "LLM extraction" demos look right on the happy path but fail silently: a swapped day/month or a wrong total goes straight into the ledger, and nobody can say how accurate the system is.

## Approach

route by file type -> read (PyMuPDF / Tesseract OCR / openpyxl / email) -> extract with one forced LLM tool call -> **validate** (arithmetic, dates, currency, source grounding) -> **targeted correction retry** (max 2) -> per-field confidence -> confident fields to JSON/CSV, uncertain fields to a **review queue** (SQLite). Every value carries `source.page` (page, `Sheet!Cell`, or `body`) and a verbatim snippet.

```
file/.eml -> ingest/router --+-- text_pdf    (PyMuPDF)
                             +-- scanned_pdf (PyMuPDF render 300 DPI -> Tesseract)
                             +-- spreadsheet (openpyxl / csv, cell refs as page refs)
                             +-- email       (stdlib email; pdf/xlsx/csv attachments re-routed)
                                   |  DocumentText: pages with [p1] / [Sheet!A3] / [body] markers
                                   v
                      extractor (Claude tool use, forced record_invoice) -> InvoiceDoc draft
                                   v
                      validator: schema, line/subtotal/total arithmetic, dates (incl. dd/mm vs mm/dd),
                                 ISO 4217, grounding of each value in its cited page
                          ok |           | issues
                             |           v
                             |   corrector: targeted prompt, only failing fields, max 2 retries
                             v           |
                      confidence = 0.5 llm + 0.3 grounding + 0.2 rules (x OCR factor on scans)
                          >= 0.7 |            | < 0.7 or still invalid
                                 v            v
                          JSON + CSV      review queue (SQLite) -> CLI / web page
                                 v
                      metrics: tokens, cost USD, ms per stage, retries
```

| Component | File |
|---|---|
| Loaders + router | `src/invoicelens/ingest/` |
| LLM layer (Anthropic, fake for tests, prompts) | `src/invoicelens/llm/` |
| Extract + correct | `src/invoicelens/extract.py` |
| Validation rules | `src/invoicelens/validate.py` |
| Confidence | `src/invoicelens/confidence.py` |
| Review queue / writer / metrics / pipeline | `review_queue.py`, `writer.py`, `metrics.py`, `pipeline.py` |
| CLI (Typer) / web (FastAPI) | `cli.py`, `web/` |
| Dataset generator / evaluation | `scripts/generate_dataset.py`, `eval/` |

## Results in numbers

Measured with `invoicelens eval` on **10 held-out synthetic documents** (3 scanned PDF, 3 text PDF, 2 email, 2 spreadsheet), model `claude-haiku-5-5`, 2026-10-17, code commit `56427c4`, dataset hash `c39e15849db64f63`. Raw files: [`reports/`](reports/). A second table covers the 40 development documents for a larger sample.

**Per-field precision / recall, baseline (single call, no validation) vs full (validation + retries + review routing).** A wrong value counts as both a false positive and a false negative.

| Field | Held-out base P / R | Held-out full P / R | Dev (n=40) base P / R | Dev (n=40) full P / R |
|---|---|---|---|---|
| supplier_name | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| document_number | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| issue_date | 1.000 / 1.000 | 1.000 / 1.000 | 0.950 / 0.950 | 0.975 / 0.975 |
| due_date | 1.000 / 1.000 | 1.000 / 1.000 | 0.967 / 0.967 | 1.000 / 1.000 |
| currency | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| doc_kind | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| subtotal | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| tax_total | 1.000 / 1.000 | 1.000 / 1.000 | 0.966 / 0.966 | 0.933 / 0.966 |
| total | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| line items (all sub-fields) | 1.000 / 0.986 | 1.000 / 0.986 | 0.998 / 0.968 | 0.998 / 0.993 |
| **overall P / R / F1** | **1.000 / 0.990 / 0.995** | **1.000 / 0.990 / 0.995** | **0.995 / 0.974 / 0.984** | **0.996 / 0.993 / 0.994** |

**Operations and review routing (full config).**

| Metric | Held-out (n=10) | Dev (n=40) |
|---|---|---|
| Cost per document, mean / p95 | $0.00102 / $0.00135 | $0.00106 / $0.00170 |
| Time per document, mean / p95 | 10.2 s / 29.7 s | 9.1 s / 27.6 s |
| Mean time by type (dev) | | scanned 18.8 s, text PDF 5.4 s, email 6.7 s, spreadsheet 5.8 s |
| Documents needing a retry | 2 of 10 | 7 of 40 |
| Fields sent to review (mean per doc) | 1.6% | 2.7% |
| Auto-accepted field precision (scalar fields) | 1.000 | 1.000 |
| Wrong scalar fields caught by review | 0 of 0 | 3 of 3 |
| Source-page accuracy | 1.000 (88 fields) | 0.997 (340 fields) |

How to read this honestly:

- **On the held-out set the baseline and the full pipeline score the same (F1 0.995).** The LLM is already very accurate on clean synthetic documents, so validation has nothing to improve there. The 3 missed items in both configs are line-item quantities left empty on two scanned documents; nothing was wrong, only missing.
- **On the 40 dev documents the full pipeline is higher (F1 0.984 to 0.994)**, mostly because retries filled in line-item fields the single call left empty. Treat that gap with caution: each configuration ran once, the LLM is not deterministic (an earlier identical-code baseline run of the dev set scored 0.994), and the validation rules were developed while looking at dev errors.
- **The main value of the full pipeline is not the F1 delta, it is that wrong values are flagged.** In the dev run every wrong scalar field (3 of 3: an OCR digit misread on a scan, a numeric date whose day/month order cannot be resolved, and a tax value the model inferred from an inconsistent printed total) landed in the review queue, and no auto-accepted scalar field was wrong. The baseline has no routing at all, so those same kinds of errors would pass silently.
- Dev-set review recall of 3 of 3 is a tiny number; do not extrapolate a rate from it.
- The held-out set was used only for final numbers, but I did read its early-run results while fixing pipeline and evaluator bugs (a line-item matcher that mis-paired duplicate descriptions, number-token parsing, spreadsheet page citations). No thresholds or weights were tuned on it.
- Threshold sensitivity (0.5 / 0.6 / 0.7 / 0.8), confidence-only, is in `reports/eval_report_full_dev.md`.

## How to run

Prerequisites: Python 3.11+, [Tesseract 5](https://github.com/UB-Mannheim/tesseract/wiki) (needed for scanned PDFs only), an Anthropic API key with a spend cap.

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                                     # then put your own key in .env (never commit it)
invoicelens generate-data                                # 50 synthetic docs + labels + split (seed 42); already committed
invoicelens extract data/synthetic/doc_044.pdf           # JSON + CSV in out/, metrics in out/metrics.jsonl
invoicelens review list                                  # pending review items
invoicelens review accept 3
invoicelens review correct 1 2026-06-11
invoicelens eval --config baseline --split heldout       # baseline vs full; writes reports/
invoicelens eval --config full --split heldout
invoicelens serve                                        # upload page on http://127.0.0.1:8000
pytest -q                                                # 74 tests, no network
```

Important: the code pins the API endpoint to `https://api.anthropic.com`. It deliberately ignores a shell-level `ANTHROPIC_BASE_URL`, because that variable can silently route your key to a proxy. To use a gateway on purpose, set `ANTHROPIC_API_BASE` in `.env`.

On Windows set `TESSERACT_CMD` in `.env` to `C:\Program Files\Tesseract-OCR\tesseract.exe`.

### Web demo and Hugging Face Space

`invoicelens serve` runs a FastAPI page: upload, result table with confidence and status colouring, click-through to the source page with the snippet highlighted (PDF) or the cell text (spreadsheet/email), a review queue page with accept/correct, and buttons that replay cached real results at zero cost. Demo caps: 2 MB, 3 pages, 20 documents per day globally, 5 uploads per minute per IP, uploads deleted after 30 minutes.

The `Dockerfile` is Space-ready (Tesseract installed, port 7860, non-root user). **Not deployed:** no Hugging Face token was available in this build. To deploy: create a Docker Space, push this repo to it, and add `ANTHROPIC_API_KEY` as a Space secret.

## Output format

`out/<doc_id>.json` carries, per field, `value`, `source {page, snippet}`, `llm_confidence`, `confidence`, `status`. `out/<doc_id>.csv` has one row per field with `source_page` and `source_link`. A complete example (a scanned invoice where Tesseract misread a digit and validation caught it) is in [`docs/examples/`](docs/examples/).

```csv
field_path,value,source_page,source_link,llm_confidence,confidence,status
total,21910.37,p1,file:///<project>/data/synthetic/doc_044.pdf#page=1,0.95,0.45,needs_review
```

## Cost per run

Prompts are well under 100K tokens, so the cheap `claude-haiku-5-5` tier applies ($0.10 input / $0.50 output per MTok, rates in `config/pricing.yaml`); the system prompt is cached.

- Measured per document: about **$0.001** (mean $0.00102 held-out, $0.00106 dev; p95 up to $0.0017).
- Full held-out evaluation (10 docs): **$0.0102**. Full dev evaluation (40 docs): **$0.0422**.
- Total spend building and measuring this project, summed over every run including the reruns after bug fixes: roughly **US$0.25 to 0.30** (estimated from per-run token logs; some earlier reports were overwritten).
- Your volume: cost is about `documents x $0.001`, plus extra for scans with many retries. 10,000 documents is on the order of $10.

## Tests

`pytest -q` runs 74 tests with a scripted fake LLM (no network): validation rules and tolerance edges, retry logic (retry then succeed, give up at 2, no retry when valid, only failing fields in the correction prompt), router and loaders for all four types, confidence scoring, writer output, matching maths, the web caps and review actions, and an end-to-end pipeline test per input type. Coverage of the core modules: `validate.py` 89%, `confidence.py` 95%, `extract.py` 98%.

## Limitations

- **Synthetic data only.** Fictional suppliers, five layouts, clean fonts. Real invoices will be messier; expect lower accuracy and more review. Measure on your own samples before trusting any number here.
- **Small held-out set** (n=10, 308 scored items). Wide uncertainty; both configurations were run once and the LLM is not deterministic.
- English only; printed text only (Tesseract, no handwriting); one invoice per file; no multi-invoice PDFs.
- OCR is the weak link: a misread digit can be self-consistent and pass every check except the arithmetic. Scans also dominate latency (about 19 s per scan vs about 6 s for digital documents).
- A numeric date such as `11/06/2026` is genuinely ambiguous unless another date in the document resolves the order; the system flags these for review rather than guessing.
- The correction retry occasionally "fixes" an inconsistent source document by changing a value to make the maths work. The field is still flagged for review, but the retry is not guaranteed to preserve the printed value.
- Confidence weights are heuristics, not calibrated probabilities.
- Email attachments are processed by the CLI/web pipeline but are not separately scored in the evaluation (the body carries the same data in the synthetic set).
- No ERP integration. Live IMAP/Gmail is out of scope; `.eml` files only.

## Data and ethics

All documents are generated by `scripts/generate_dataset.py` (Faker + ReportLab + openpyxl, seed 42). No client or real supplier data.

## License

MIT. See `LICENSE`.
