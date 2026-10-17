"""Typer CLI: generate-data, extract, eval, review, serve."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .settings import PROJECT_ROOT, get_settings

app = typer.Typer(help="InvoiceLens: invoice & PO extraction with measured accuracy.", no_args_is_help=True)
review_app = typer.Typer(help="Review queue commands.", no_args_is_help=True)
app.add_typer(review_app, name="review")


def _get_llm():
    cfg = get_settings()
    if cfg.llm_provider == "anthropic":
        from .llm.anthropic_client import AnthropicClient

        return AnthropicClient()
    raise typer.BadParameter(f"unsupported llm_provider: {cfg.llm_provider}")


@app.command("generate-data")
def generate_data(seed: int = typer.Option(42, help="Random seed.")):
    """Generate the 50-document synthetic dataset + labels + splits."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from generate_dataset import generate  # type: ignore

    generate(seed=seed, out_root=PROJECT_ROOT / "data")
    typer.echo(f"Dataset written to {PROJECT_ROOT / 'data'}")


@app.command()
def extract(
    path: Path = typer.Argument(..., help="File to extract (.pdf/.xlsx/.csv/.eml)."),
    config: str = typer.Option("full", help="baseline | full."),
    out: Path = typer.Option(PROJECT_ROOT / "out", help="Output directory."),
):
    """Extract one document to JSON + CSV."""
    from .metrics import append_metrics
    from .pipeline import process_document
    from .review_queue import init_db

    init_db()
    llm = _get_llm()
    results = process_document(llm, path, config=config, write_outputs=True, out_dir=out)
    for r in results:
        if r.error:
            typer.echo(f"[error] {r.doc_id}: {r.error}")
            continue
        d = r.doc.model_dump() if r.doc else {}
        total = d.get("total", {})
        typer.echo(
            f"{r.doc_id} ({r.doc_type}): total={total.get('value')} "
            f"cost=${r.metrics.cost_usd:.4f} retries={r.metrics.retries} "
            f"needs_review={r.metrics.fields_needs_review}/{r.metrics.fields_total}"
        )
        if r.metrics:
            append_metrics(out / "metrics.jsonl", r.metrics)


@app.command()
def eval(
    config: str = typer.Option("full", help="baseline | full."),
    split: str = typer.Option("heldout", help="dev | heldout."),
    limit: int = typer.Option(0, help="Limit number of docs (0 = all)."),
    report: bool = typer.Option(True, help="Write reports/eval_*.json."),
):
    """Run the held-out (or dev) evaluation and print per-field P/R."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "eval"))
    from evaluate import run_eval  # type: ignore

    result = run_eval(config=config, split=split, limit=limit, write_report=report)
    typer.echo(json.dumps(result["aggregate"], indent=2))


@review_app.command("list")
def review_list():
    """List pending review items."""
    from .review_queue import init_db, list_pending

    init_db()
    items = list_pending()
    if not items:
        typer.echo("no pending items")
        return
    for it in items:
        typer.echo(
            f"#{it.id} {it.doc_id} {it.field_path} = {it.suggested_value!r} "
            f"conf={it.confidence:.2f} src={it.source_page}"
        )
        for iss in it.issues:
            typer.echo(f"    {iss}")


@review_app.command("accept")
def review_accept(item_id: int = typer.Argument(..., help="Review item id.")):
    """Accept the suggested value of an item."""
    from .review_queue import accept, init_db

    init_db()
    accept(item_id)
    typer.echo(f"accepted {item_id}")


@review_app.command("correct")
def review_correct(
    item_id: int = typer.Argument(..., help="Review item id."),
    value: str = typer.Argument(..., help="Corrected value."),
):
    """Replace the suggested value with a corrected one."""
    from .review_queue import correct_item, init_db

    init_db()
    correct_item(item_id, value)
    typer.echo(f"corrected {item_id} -> {value}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Start the FastAPI demo upload page."""
    import uvicorn

    uvicorn.run("invoicelens.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
