# Demo video script (2 minutes maximum)

Record with OBS Studio (free). Screen only, voice-over optional. Say "synthetic data" once near the start. All numbers below are from `reports/` (run on 2026-10-17, model `claude-haiku-5-5`); re-read them from the files before recording if you re-run the eval.

Prep: `invoicelens serve` running; `data/review.db` seeded by running `invoicelens extract` on `data/synthetic/doc_044.pdf`, `doc_017.pdf`, `doc_002.pdf` (these produce the review items shown at 1:10). Terminal open in the project folder.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:12 | Title card, then the upload page | "Invoices arrive as PDFs, scans, spreadsheets and emails. This pipeline extracts them into a fixed schema and tells you how much to trust each field. It is measured on synthetic data." |
| 0:12-0:35 | Click the cached sample `doc_016 (text PDF)`; result table; click the source link on `total` | "A text PDF in, validated fields out. Each value has a confidence and a source page. Click a field and you see the page with the cited text highlighted." |
| 0:35-0:55 | Cached sample `doc_034 (scanned PDF)` | "A scan: rendered, OCR'd with Tesseract, then the same extraction. Scans take about 19 seconds, digital documents about 6." |
| 0:55-1:10 | Terminal: `invoicelens extract data/synthetic/doc_015.eml` showing the email and its PDF attachment processed as two documents, then open the CSV | "An email whose body carries the order and a PDF attached: both are processed. Output is JSON plus a CSV with source links." |
| 1:10-1:30 | Browser `/review` | "This scan has a digit misread by OCR. The arithmetic check caught that subtotal plus tax does not equal the total, so the field is not trusted: it lands here with the reason and the source snippet. Accept or correct." Click Correct on one item. |
| 1:30-1:50 | Terminal: `invoicelens eval --config full --split heldout` output, or `reports/eval_report_full_dev.md` | "On 40 development documents the full pipeline scores F1 0.994 against 0.984 for a plain single call, and every wrong scalar field was routed to review. On the 10 held-out documents both score 0.995. Cost is about a tenth of a cent per document." |
| 1:50-2:00 | Repo / README results table | "Code, tests and the measured report are in the repo. Available as a fixed-scope build on Upwork." |

Do not claim: production accuracy, real customer data, or that the live Hugging Face Space exists (it has not been deployed yet).
