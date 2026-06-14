"""Export the dashboard ``kpi_*`` tables to CSV — a no-ODBC fallback for BI tools.

If the Hive ODBC driver is troublesome, run this to dump every KPI table from both
warehouses to ``dashboard/exports/*.csv``, then load them in Tableau / Power BI via
*Get Data -> Text/CSV*.

Connects to HiveServer2 over JDBC/Thrift using ``pyhive`` (in requirements.txt).
Host/port come from ``.env`` (``HIVESERVER2_HOST`` / ``HIVESERVER2_PORT``) or default
to ``localhost:10000``.

Run (Hive stack must be up; from the host or inside the spark image)::

    python dashboard/export_kpis_csv.py

If ``pyhive`` is unavailable, the script prints ready-to-paste ``beeline`` commands.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "dashboard" / "exports"

# (database, table) pairs created by warehouse/dashboard_kpis.sql
KPI_TABLES = ["kpi_overall", "kpi_default_by_demographic",
              "kpi_monthly_default_vs_macro", "kpi_corr_default_macro"]
DATABASES = ["bigdata_etl", "bigdata_elt"]   # ETL -> Tableau, ELT -> Power BI


def _beeline_hint() -> None:
    print("\npyhive not available — use beeline instead (one per table):\n")
    for db in DATABASES:
        for tbl in KPI_TABLES:
            print(f'docker compose exec hiveserver2 beeline -u "jdbc:hive2://localhost:10000" '
                  f'--outputformat=csv2 -e "SELECT * FROM {db}.{tbl};" '
                  f'> dashboard/exports/{db}__{tbl}.csv')


def main() -> int:
    try:
        from pyhive import hive  # type: ignore
    except ImportError:
        _beeline_hint()
        return 1

    host = os.getenv("HIVESERVER2_HOST", "localhost")
    port = int(os.getenv("HIVESERVER2_PORT", "10000"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        conn = hive.Connection(host=host, port=port, username="hive")
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to HiveServer2 at {host}:{port} ({exc}).")
        _beeline_hint()
        return 1

    written = 0
    for db in DATABASES:
        for tbl in KPI_TABLES:
            try:
                cur = conn.cursor()
                cur.execute(f"SELECT * FROM {db}.{tbl}")
                rows = cur.fetchall()
                cols = [d[0].split(".")[-1] for d in cur.description]
                out = OUT_DIR / f"{db}__{tbl}.csv"
                with out.open("w", newline="", encoding="utf-8") as fh:
                    w = csv.writer(fh)
                    w.writerow(cols)
                    w.writerows(rows)
                print(f"OK  {out.relative_to(REPO_ROOT)}  ({len(rows)} rows)")
                written += 1
            except Exception as exc:  # noqa: BLE001
                print(f"skip {db}.{tbl}: {exc}")
    print(f"\nDone: {written}/{len(DATABASES) * len(KPI_TABLES)} CSV files in {OUT_DIR}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
