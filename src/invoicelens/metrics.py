"""Cost + time accounting. Appends RunMetrics to out/metrics.jsonl."""

from __future__ import annotations

import time
from pathlib import Path

from .models import RunMetrics, Usage
from .settings import get_pricing


def usage_cost(usage: Usage, model: str) -> float:
    p = get_pricing(model)
    inp = p.get("input_per_mtok", 0.10)
    out = p.get("output_per_mtok", 0.50)
    cw = p.get("cache_write_per_mtok", inp * 1.25)
    cr = p.get("cache_read_per_mtok", inp * 0.1)
    return (
        usage.input_tokens * inp
        + usage.cache_creation_input_tokens * cw
        + usage.cache_read_input_tokens * cr
        + usage.output_tokens * out
    ) / 1_000_000


def add_usage(a: Usage, b: Usage) -> Usage:
    return Usage(
        input_tokens=a.input_tokens + b.input_tokens,
        output_tokens=a.output_tokens + b.output_tokens,
        cache_read_input_tokens=a.cache_read_input_tokens + b.cache_read_input_tokens,
        cache_creation_input_tokens=a.cache_creation_input_tokens + b.cache_creation_input_tokens,
    )


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)


def append_metrics(path: str | Path, metrics: RunMetrics) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(metrics.model_dump_json() + "\n")
