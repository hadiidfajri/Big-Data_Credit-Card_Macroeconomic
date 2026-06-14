"""Per-stage runtime & resource instrumentation (Prompt 9).

Every pipeline stage wraps its work in :func:`stage_timer`, which records wall
duration and peak memory (via ``psutil`` if available) and appends one JSON record
per stage to ``logs/pipeline_metrics.jsonl``. The comparison generator
(``analysis/compare_pipelines.py``) reads that file to build the ETL-vs-ELT table.

Example::

    with stage_timer("ETL", "transform", logger) as m:
        ...
        m.rows = df.count()
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterator

from common.paths import METRICS_FILE

try:  # optional dependency — degrade gracefully if missing
    import psutil

    _PROC = psutil.Process(os.getpid())
except Exception:  # noqa: BLE001
    psutil = None
    _PROC = None


@dataclass
class StageMetric:
    """One measured pipeline stage."""

    pipeline: str          # "ETL" | "ELT"
    stage: str             # extract | transform | load | ...
    status: str = "OK"
    rows: int | None = None
    duration_s: float = 0.0
    peak_rss_mb: float | None = None
    extra: dict = field(default_factory=dict)
    ts: str = ""


def _rss_mb() -> float | None:
    if _PROC is None:
        return None
    try:
        return round(_PROC.memory_info().rss / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        return None


def record(metric: StageMetric) -> StageMetric:
    """Append a fully-populated metric to the JSONL metrics file."""
    metric.ts = metric.ts or datetime.now(timezone.utc).isoformat()
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(metric)) + "\n")
    return metric


@contextmanager
def stage_timer(pipeline: str, stage: str, logger=None, **extra) -> Iterator[StageMetric]:
    """Time a stage, capture peak RSS, persist a metric, and re-raise on error."""
    metric = StageMetric(pipeline=pipeline, stage=stage, extra=dict(extra))
    start = time.perf_counter()
    rss_start = _rss_mb()
    try:
        yield metric
    except Exception as exc:  # noqa: BLE001
        metric.status = "FAILED"
        metric.extra["error"] = str(exc)
        raise
    finally:
        metric.duration_s = round(time.perf_counter() - start, 3)
        rss_end = _rss_mb()
        if rss_start is not None and rss_end is not None:
            metric.peak_rss_mb = max(rss_start, rss_end)
        record(metric)
        if logger is not None:
            logger.info(
                "[%s/%s] status=%s rows=%s duration=%.2fs peak_rss=%sMB",
                pipeline, stage, metric.status, metric.rows,
                metric.duration_s, metric.peak_rss_mb,
            )
