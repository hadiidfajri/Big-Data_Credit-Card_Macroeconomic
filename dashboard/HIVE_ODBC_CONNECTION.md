# Hive ODBC Connection Guide — Tableau (ETL) & Power BI (ELT)

Both BI tools connect to the **same HiveServer2** endpoint exposed by the Docker stack
and read the materialised `kpi_*` tables. Tableau binds to `bigdata_etl`, Power BI to
`bigdata_elt` — identical table names, identical dashboard design (CLAUDE.md §8).

## 0. Prerequisites
1. Stack running: `docker compose up -d` (need `hiveserver2` healthy).
2. Pipelines built so the KPI tables exist:
   ```powershell
   docker compose exec spark-master spark-submit /app/etl_pipeline/transform.py
   docker compose exec spark-master spark-submit /app/etl_pipeline/load.py
   docker compose exec spark-master spark-submit /app/elt_pipeline/extract_load.py
   docker compose exec spark-master spark-submit /app/elt_pipeline/run_transform.py
   docker compose exec spark-master spark-submit /app/dashboard/build_dashboard_kpis.py
   ```
3. Install the **Hive ODBC driver** (Cloudera/Microsoft Hive ODBC, 64-bit) on Windows.

## 1. Connection parameters
| Field           | Value                          |
|-----------------|--------------------------------|
| Host            | `localhost`                    |
| Port            | `10000`                        |
| Database        | `bigdata_etl` (Tableau) / `bigdata_elt` (Power BI) |
| Authentication  | `No Authentication` / `User Name` = `hive` |
| Hive Server Type| `HiveServer2`                  |
| Transport       | `SASL` (default) — if it fails, try `Binary`/`No SASL` |
| Thrift Transport| `SASL`                         |

> Quick check from the host before wiring up the BI tool:
> ```powershell
> docker compose exec hiveserver2 beeline -u "jdbc:hive2://localhost:10000" -e "SHOW TABLES IN bigdata_etl LIKE 'kpi_*';"
> ```

## 2. Tableau (→ ETL warehouse)
1. **Connect → To a Server → More → Hortonworks Hadoop Hive** (or "Other Databases (ODBC)" → your Hive DSN).
2. Server `localhost`, Port `10000`, Authentication `Username`, Username `hive`.
3. Schema `bigdata_etl` → drag in `kpi_overall`, `kpi_default_by_demographic`,
   `kpi_monthly_default_vs_macro`, `kpi_corr_default_macro`.
4. Use a **live** connection (small KPI tables) or extract for snappier interactivity.
5. Save as `dashboard/tableau_etl_dashboard.twbx`.

## 3. Power BI (→ ELT warehouse)
1. **Get Data → ODBC** (configure a Hive DSN first in *ODBC Data Sources (64-bit)*),
   or **Get Data → More → Other → Hive** if your build exposes it.
2. DSN points at `localhost:10000`, database `bigdata_elt`.
3. Load the same four `kpi_*` tables.
4. Prefer **Import** mode (KPI tables are tiny); DirectQuery also works.
5. Save as `dashboard/powerbi_elt_dashboard.pbix`.

## 4. Troubleshooting
- **Driver not listed** → install the 64-bit Hive ODBC driver, restart the BI tool.
- **SASL handshake error** → switch Thrift transport to `Binary` / `No SASL` (the
  containerised HiveServer2 runs without Kerberos).
- **Empty schema** → the KPI tables weren't built; re-run step 0.2.
- **Slow first query** → HiveServer2 cold start; retry once it has warmed up.

> ⚠️ The `.twbx` / `.pbix` themselves are assembled in the desktop apps. This repo
> prepares the data, the KPI tables, the connection, and the spec — the final visuals
> are built by hand (see `DASHBOARD_SPEC.md`).
