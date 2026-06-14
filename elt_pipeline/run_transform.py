"""Prompt 7 — execute the ELT in-warehouse transform (``transform.sql``).

Runs the set-based HiveQL/Spark SQL in ``elt_pipeline/transform.sql`` against the
``bigdata_elt`` raw tables, materialising the analytical tables. Derived tables are
dropped first so re-runs are idempotent. Timed via ``common.metrics``.

Run::

    docker compose exec spark-master spark-submit /app/elt_pipeline/run_transform.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.metrics import stage_timer  # noqa: E402
from common.paths import ELT_DIR, ELT_LOGS  # noqa: E402
from common.spark_session import get_spark  # noqa: E402

logger = get_logger("elt.transform", ELT_LOGS / "transform.log")

DB = "bigdata_elt"
SQL_FILE = ELT_DIR / "transform.sql"
DERIVED = [
    "elt_macro_monthly", "elt_fact_monthly", "elt_client_trends",
    "elt_default_by_demographic", "elt_default_vs_macro",
]


def parse_statements(sql_text: str) -> list[str]:
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    spark = get_spark("elt-transform", with_hive=True)
    logger.info("=== ELT Transform started (db=%s) ===", DB)

    with stage_timer("ELT", "transform", logger) as m:
        for tbl in DERIVED:                       # idempotent re-runs
            spark.sql(f"DROP TABLE IF EXISTS {DB}.{tbl}")

        statements = parse_statements(SQL_FILE.read_text(encoding="utf-8"))
        logger.info("Executing %d ELT statements", len(statements))
        for i, stmt in enumerate(statements, 1):
            logger.info("--- statement %d ---", i)
            spark.sql(stmt)

        total = 0
        for tbl in DERIVED:
            n = spark.table(f"{DB}.{tbl}").count()
            total += n
            logger.info("materialised %s.%s rows=%d", DB, tbl, n)
        m.rows = total

        logger.info("Sample — default rate by demographic:")
        spark.sql(f"SELECT * FROM {DB}.elt_default_by_demographic ORDER BY clients DESC").show(30, False)

    logger.info("=== ELT Transform finished ===")
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
