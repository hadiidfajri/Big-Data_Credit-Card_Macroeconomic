"""Prompt 6 — ETL Load (Hive), per CLAUDE.md §6.3.

Builds the **star schema** in Hive from the Transform parquet output, applies
PK/FK (informational) constraints, then runs the **8 analytical queries** from
``warehouse/etl_analytical_queries.sql``. Status + duration are logged/metered.

Tables (database ``bigdata_etl``):
``fact_credit_monthly`` (client × month) → ``dim_client``, ``dim_date``;
``dim_macro`` linked via ``dim_date``.

Run::

    docker compose exec spark-master spark-submit /app/etl_pipeline/load.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.metrics import stage_timer  # noqa: E402
from common.paths import ETL_LOGS, STAGING_DIR, WAREHOUSE_DIR  # noqa: E402
from common.spark_session import get_spark  # noqa: E402

logger = get_logger("etl.load", ETL_LOGS / "load.log")

DB = "bigdata_etl"
TABLES = ["dim_client", "dim_date", "dim_macro", "fact_credit_monthly"]
QUERIES_FILE = WAREHOUSE_DIR / "etl_analytical_queries.sql"

CONSTRAINTS = [
    f"ALTER TABLE {DB}.dim_client ADD CONSTRAINT pk_client PRIMARY KEY (id) DISABLE NOVALIDATE RELY",
    f"ALTER TABLE {DB}.dim_date ADD CONSTRAINT pk_date PRIMARY KEY (date_key) DISABLE NOVALIDATE RELY",
    f"ALTER TABLE {DB}.dim_macro ADD CONSTRAINT pk_macro PRIMARY KEY (date_key) DISABLE NOVALIDATE RELY",
    f"ALTER TABLE {DB}.fact_credit_monthly ADD CONSTRAINT fk_fact_client "
    f"FOREIGN KEY (id) REFERENCES {DB}.dim_client(id) DISABLE NOVALIDATE RELY",
    f"ALTER TABLE {DB}.fact_credit_monthly ADD CONSTRAINT fk_fact_date "
    f"FOREIGN KEY (date_key) REFERENCES {DB}.dim_date(date_key) DISABLE NOVALIDATE RELY",
]


def load_tables(spark) -> None:
    # Drop + recreate so re-runs are idempotent (a half-finished prior run can leave
    # managed-table dirs behind -> LOCATION_ALREADY_EXISTS on saveAsTable).
    spark.sql(f"DROP DATABASE IF EXISTS {DB} CASCADE")
    spark.sql(f"CREATE DATABASE {DB}")
    for tbl in TABLES:
        path = STAGING_DIR / tbl
        if not path.exists():
            raise FileNotFoundError(f"Missing staging table {path} — run transform.py first.")
        df = spark.read.parquet(str(path))
        df.write.mode("overwrite").format("parquet").saveAsTable(f"{DB}.{tbl}")
        logger.info("Loaded %s.%s rows=%d cols=%d", DB, tbl, df.count(), len(df.columns))


def apply_constraints(spark) -> None:
    for stmt in CONSTRAINTS:
        try:
            spark.sql(stmt)
        except Exception as exc:  # noqa: BLE001 — informational; metastore may reject duplicates
            logger.warning("Constraint skipped (%s): %s", stmt.split("ADD CONSTRAINT")[1][:24], exc)


def parse_statements(sql_text: str) -> list[str]:
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def run_queries(spark) -> None:
    statements = parse_statements(QUERIES_FILE.read_text(encoding="utf-8"))
    logger.info("Running %d analytical queries from %s", len(statements), QUERIES_FILE.name)
    for i, stmt in enumerate(statements, 1):
        logger.info("--- Q%d ---\n%s", i, stmt)
        result = spark.sql(stmt)
        result.show(30, truncate=False)


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    spark = get_spark("etl-load", with_hive=True)
    logger.info("=== ETL Load started (db=%s) ===", DB)

    with stage_timer("ETL", "load", logger) as m:
        load_tables(spark)
        apply_constraints(spark)
        run_queries(spark)
        m.rows = spark.table(f"{DB}.fact_credit_monthly").count()

    logger.info("=== ETL Load finished (fact rows=%d) ===", m.rows)
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
