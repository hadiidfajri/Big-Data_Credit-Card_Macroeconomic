"""Prompt 7 — ELT Extract+Load: land the raw sources into Hive **untransformed**.

The ELT philosophy: load first, transform later *inside* the warehouse. This
script pulls the same sources as the ETL path and writes them to Hive **raw**
tables with **no cleaning / no feature engineering** (only column identifiers are
made warehouse-safe — a structural requirement, not a data change). The actual
transformation happens in ``transform.sql`` (run by ``run_transform.py``).

Raw tables (database ``bigdata_elt``):
* ``raw_credit`` — the wide credit table, values untouched.
* ``raw_macro``  — FRED observations in long form (series_id, obs_date, value).

Load metadata (rows, cols, size) is logged and written to
``elt_pipeline/logs/load_metadata.json``.

Run::

    docker compose exec spark-master spark-submit /app/elt_pipeline/extract_load.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import (  # noqa: E402
    StringType, StructField, StructType,
)

from common.logging_utils import get_logger  # noqa: E402
from common.metrics import stage_timer  # noqa: E402
from common.paths import ELT_LOGS, RAW_DIR, SYNTHETIC_DIR, ensure_dirs  # noqa: E402
from common.spark_session import get_spark  # noqa: E402

logger = get_logger("elt.extract_load", ELT_LOGS / "extract_load.log")

DB = "bigdata_elt"
FRED_SERIES = ["EXTAUS", "RBTWBIS", "NBTWBIS", "TRESEGTWM194N"]


def _safe(name: str) -> str:
    """Warehouse-safe identifier (structural only — no value change)."""
    return re.sub(r"__+", "_", re.sub(r"\W+", "_", name.strip())).lower().strip("_")


def load_raw_credit(spark) -> dict:
    # Source 1 = synthetic credit clients placed in raw/ (CTGAN skipped from the run).
    candidates = [
        RAW_DIR / "synthetic_credit_clients.csv",
        SYNTHETIC_DIR / "synthetic_credit_clients.csv",
        RAW_DIR / "uci_credit_card.csv",
    ]
    src = next((p for p in candidates if p.exists()), candidates[0])
    if not src.exists():
        raise FileNotFoundError("No credit CSV found (synthetic or raw). Run upstream stages.")
    df = spark.read.csv(str(src), header=True, inferSchema=True)
    for c in df.columns:                       # warehouse-safe names only
        df = df.withColumnRenamed(c, _safe(c))
    df.write.mode("overwrite").format("parquet").saveAsTable(f"{DB}.raw_credit")
    logger.info("raw_credit <- %s rows=%d cols=%d", src.name, df.count(), len(df.columns))
    return {"table": "raw_credit", "source": src.name, "rows": df.count(),
            "cols": len(df.columns), "size_bytes": src.stat().st_size}


def load_raw_macro(spark) -> dict:
    rows = []
    for series_id in FRED_SERIES:
        path = RAW_DIR / f"fred_{series_id}_2005.json"
        if not path.exists():
            logger.warning("Missing %s — skipped.", path.name)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for o in payload.get("observations", []):
            rows.append((series_id, o.get("date"), str(o.get("value"))))

    schema = StructType([
        StructField("series_id", StringType()),
        StructField("obs_date", StringType()),
        StructField("value", StringType()),   # raw string, '.' preserved (no cleaning)
    ])
    df = spark.createDataFrame(rows, schema)
    df.write.mode("overwrite").format("parquet").saveAsTable(f"{DB}.raw_macro")
    logger.info("raw_macro rows=%d (series=%d)", df.count(), len(FRED_SERIES))
    return {"table": "raw_macro", "source": "fred_*_2005.json",
            "rows": df.count(), "cols": len(df.columns)}


def main() -> int:
    ensure_dirs(ELT_LOGS)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    spark = get_spark("elt-extract-load", with_hive=True)
    logger.info("=== ELT Extract+Load started (db=%s) ===", DB)

    with stage_timer("ELT", "extract_load", logger) as m:
        # Drop + recreate so re-runs are idempotent (avoids LOCATION_ALREADY_EXISTS
        # from managed-table dirs left by a prior run).
        spark.sql(f"DROP DATABASE IF EXISTS {DB} CASCADE")
        spark.sql(f"CREATE DATABASE {DB}")
        meta = [load_raw_credit(spark), load_raw_macro(spark)]
        m.rows = sum(x["rows"] for x in meta)
        (ELT_LOGS / "load_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info("=== ELT Extract+Load finished (rows=%d) ===", m.rows)
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
