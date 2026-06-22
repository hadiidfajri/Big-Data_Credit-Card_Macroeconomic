"""Prompt 8 — build the dashboard KPI tables from ``warehouse/dashboard_kpis.sql``.

Executes the KPI DDL against Hive via Spark, materialising the identical ``kpi_*``
tables in both ``bigdata_etl`` (ETL) and ``bigdata_elt`` (ELT). Requires
the ETL Load and the ELT transform to have run first.

Run::

    docker compose exec spark-master spark-submit /app/dashboard/build_dashboard_kpis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.paths import DASHBOARD_DIR, WAREHOUSE_DIR  # noqa: E402
from common.spark_session import get_spark  # noqa: E402

logger = get_logger("dashboard.kpis", DASHBOARD_DIR / "build_kpis.log")
SQL_FILE = WAREHOUSE_DIR / "dashboard_kpis.sql"


def parse_statements(sql_text: str) -> list[str]:
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    spark = get_spark("dashboard-kpis", with_hive=True)
    logger.info("=== Building dashboard KPI tables ===")

    statements = parse_statements(SQL_FILE.read_text(encoding="utf-8"))
    for i, stmt in enumerate(statements, 1):
        logger.info("--- KPI statement %d ---", i)
        spark.sql(stmt)

    for db in ("bigdata_etl", "bigdata_elt"):
        logger.info("KPI tables in %s:", db)
        spark.sql(f"SHOW TABLES IN {db} LIKE 'kpi_*'").show(truncate=False)
    logger.info("=== Dashboard KPI tables built ===")
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
