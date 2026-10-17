"""Pipeline: process_document(path) -> PipelineResult.

config: "baseline" (single call, no validation/retry/review) or "full"
(extraction + validation + up to max_retries targeted retries + review routing).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .confidence import iter_fields, score_doc
from .extract import correct, extract
from .ingest import email_msg, router, scanned_pdf, spreadsheet, text_pdf
from .metrics import Timer, add_usage, usage_cost
from .models import DocumentText, PipelineResult, RunMetrics, Usage
from .settings import get_settings
from .validate import validate_doc

MARKERS = {
    "text_pdf": text_pdf.marked_text,
    "scanned_pdf": scanned_pdf.marked_text,
    "spreadsheet": spreadsheet.marked_text,
    "email": email_msg.marked_text,
}


def _load(path: Path, doc_id: str | None = None) -> tuple[DocumentText, list[Path]]:
    """Load a file into DocumentText + any extracted attachment paths."""
    dtype = router.detect(path)
    if dtype == "text_pdf":
        return text_pdf.load(path, doc_id), []
    if dtype == "scanned_pdf":
        return scanned_pdf.load(path, doc_id), []
    if dtype == "spreadsheet":
        return spreadsheet.load(path, doc_id), []
    if dtype == "email":
        tmp = Path(tempfile.mkdtemp(prefix="invoicelens_atts_"))
        doc, atts = email_msg.load(path, doc_id, extract_attachments_to=str(tmp))
        return doc, [a.saved_path for a in atts]
    raise ValueError(f"cannot load type {dtype}")


def _process_one(
    llm,
    path: Path,
    doc_id: str,
    config: str,
    write_outputs: bool = False,
    out_dir: str | Path | None = None,
    db_path: str | Path | None = None,
) -> tuple[PipelineResult, list[Path]]:
    cfg = get_settings()
    t_total = Timer()
    t_ingest = Timer()
    doc_text, attachments = _load(path, doc_id)
    ms_ingest = t_ingest.ms()

    marked = MARKERS[doc_text.doc_type](doc_text)

    t_llm = Timer()
    usage = Usage()
    retries = 0
    issues = []
    try:
        doc, u = extract(llm, doc_id, doc_text.doc_type, marked)
        usage = add_usage(usage, u)

        if config == "full":
            t_val = Timer()
            page_texts = {p.ref: p.text for p in doc_text.pages}
            issues = validate_doc(doc, page_texts, cfg.grounding.fuzzy_threshold)
            def _retriable(iss):
                return [i for i in iss if i.code != "date_ambiguous"]

            while _retriable(issues) and retries < cfg.max_retries:
                u2 = correct(llm, doc, doc_text.doc_type, marked, _retriable(issues))
                usage = add_usage(usage, u2)
                retries += 1
                issues = validate_doc(doc, page_texts, cfg.grounding.fuzzy_threshold)
            ms_validate = t_val.ms()
            score_doc(doc, doc_text, issues)
            from .review_queue import add_items

            add_items(doc, issues, db_path)
        else:
            # baseline: still score for output consistency, but no retry/review routing
            ms_validate = 0
            score_doc(doc, doc_text, [])
            issues = []
    except Exception as e:  # noqa: BLE001 - surface as PipelineResult.error
        ms_llm = t_llm.ms()
        return (
            PipelineResult(
                doc_id=doc_id,
                doc_type=doc_text.doc_type,
                doc=None,
                issues=[],
                metrics=RunMetrics(
                    doc_id=doc_id,
                    doc_type=doc_text.doc_type,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=usage_cost(usage, cfg.llm_model),
                    ms_ingest=ms_ingest,
                    ms_llm=ms_llm,
                    ms_total=t_total.ms(),
                    retries=retries,
                ),
                error=str(e),
            ),
            attachments,
        )

    ms_llm = t_llm.ms()

    fields_total = 0
    fields_nr = 0
    if doc is not None:
        for _, f in iter_fields(doc):
            fields_total += 1
            if f.status == "needs_review":
                fields_nr += 1

    metrics = RunMetrics(
        doc_id=doc_id,
        doc_type=doc_text.doc_type,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_input_tokens=usage.cache_read_input_tokens,
        cache_creation_input_tokens=usage.cache_creation_input_tokens,
        cost_usd=usage_cost(usage, cfg.llm_model),
        ms_ingest=ms_ingest,
        ms_llm=ms_llm,
        ms_validate=locals().get("ms_validate", 0),
        ms_total=t_total.ms(),
        retries=retries,
        fields_total=fields_total,
        fields_needs_review=fields_nr,
    )

    if write_outputs and out_dir is not None and doc is not None:
        from .writer import write

        write(doc, doc_text, out_dir)

    return (
        PipelineResult(
            doc_id=doc_id,
            doc_type=doc_text.doc_type,
            doc=doc,
            issues=issues,
            metrics=metrics,
            error=None,
        ),
        attachments,
    )


def _att_name(att: Path, doc_id: str) -> str:
    """Attachment stem without the '<doc_id>_' prefix the email loader adds when saving it."""
    stem = att.stem
    return stem[len(doc_id) + 1 :] if stem.startswith(doc_id + "_") else stem


def process_document(
    llm,
    path: str | Path,
    config: str = "full",
    doc_id: str | None = None,
    write_outputs: bool = False,
    out_dir: str | Path | None = None,
    db_path: str | Path | None = None,
    include_attachments: bool = True,
) -> list[PipelineResult]:
    """Process one file. An email with attachments yields one result per attachment too."""
    p = Path(path)
    doc_id = doc_id or p.stem
    results: list[PipelineResult] = []
    first, attachments = _process_one(llm, p, doc_id, config, write_outputs, out_dir, db_path)
    results.append(first)
    for att in attachments if include_attachments else []:
        try:
            att_id = f"{doc_id}__{_att_name(att, doc_id)}"
            r, _ = _process_one(llm, att, att_id, config, write_outputs, out_dir, db_path)
            results.append(r)
        except Exception as e:  # noqa: BLE001
            results.append(
                PipelineResult(doc_id=f"{doc_id}__{_att_name(att, doc_id)}", doc_type="?", doc=None, error=str(e))
            )
    return results
