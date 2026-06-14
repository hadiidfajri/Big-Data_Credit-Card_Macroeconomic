# CLAUDE.md

> Project context file for **Tugas Besar Big Data** — ETL & ELT Pipeline + Analytics Dashboard.
> This file guides any agent/contributor working in this repo. Keep it updated as decisions are made.
> All major design decisions are **CONFIRMED** unless explicitly marked **[OPEN]**.

---

## 1. Project Overview

- **Course:** Big Data (Final Project / Tugas Besar)
- **Deliverable:** ETL pipeline + ELT pipeline + interactive analytics dashboard + report
- **Semester:** GENAP 2025/2026.
- **Mode:** Group of **2** members.

### Chosen Topic
**No. 7 — Analitik Keuangan dan Transaksi Digital.**

### Problem Context & Analytical Goal
Analyze **credit card default risk in Taiwan** and relate borrower behavior to the **macroeconomic environment** (FRED Taiwan series, 2005). The pipeline + dashboard answer: who defaults, which payment/billing patterns predict default, and how default risk correlates with macro indicators (interest rates, exchange rate, money/reserves).

---

## 2. Tech Stack

| Stage | Tool | Notes |
|-------|------|-------|
| **Extract** | Apache Kafka | Producers read source files/API → publish to topics; consumers persist raw data to `raw/` and `datalake/`. |
| **Transform** | Apache Spark (PySpark) + Apache Hive | Spark (`local[*]`) for ETL transforms. Hive/Spark SQL for ELT in-warehouse transforms. |
| **Data Warehouse** | Apache Hive | **CONFIRMED** — Hive is the warehouse (tables on local warehouse dir / HDFS). |
| **Dashboard** | Tableau (ETL) + Power BI (ELT) | **Tableau** → **ETL** warehouse output; **Power BI** → **ELT** warehouse output. Same dashboard design in both. Connection via **Hive ODBC**. |
| **Synthetic Data** | CTGAN | Generate **≥150,000 synthetic credit clients**, applied **before** the FRED merge. |
| **Language** | Python 3.x | PySpark, pandas, sdv (CTGAN), fredapi/requests. |
| **Deployment** | **Docker Compose** | Kafka (+ Zookeeper/KRaft), Spark, Hive metastore in containers. |

> Pipeline-to-dashboard mapping: ETL star schema → **Tableau**; ELT transformed tables → **Power BI**. Identical KPIs/visuals so the two pipelines can be compared visually.

---

## 3. Datasets

### Dataset 1 — Primary (credit, becomes monthly after unpivot)
- **Default of Credit Card Clients (Taiwan)** — UCI ML Repository (id 350)
- `https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients`
- Format: **XLSX / CSV**
- ~30,000 rows, 23 features + 1 target (`default payment next month`). Billing history Apr–Sep 2005.
- **Wide → long mapping (used for monthly grain):** each client holds 6 months of history.
  - `PAY_0`→Sep, `PAY_2`→Aug, `PAY_3`→Jul, `PAY_4`→Jun, `PAY_5`→May, `PAY_6`→Apr (note: no `PAY_1` exists — dataset quirk).
  - `BILL_AMT1..6` → Sep…Apr 2005; `PAY_AMT1..6` → Sep…Apr 2005.

### Dataset 2 — Secondary (monthly time series, enrichment)
- **FRED — Federal Reserve Economic Data (Taiwan)** — `https://fred.stlouisfed.org/categories/32438`
- Access: **FRED API (JSON)** → counts as the 2nd format alongside UCI XLSX/CSV (bonus, brief §4).
- **Date range: 2005 only.**
- **⚠️ FRED reality (VERIFIED):** FRED's monthly Taiwan coverage is thin and is essentially **exchange rates + reserves**. Headline indicators (CPI, unemployment, GDP, retail sales, wages) are annual/quarterly on FRED for Taiwan → constant across 2005, useless at monthly grain. **No monthly interest rate exists for Taiwan on FRED** (IMF discount rate `INTDSRTWM193N` not confirmed; OECD interbank/call-money rates cover Korea/Japan/etc. but not Taiwan, a non-OECD member).
- **Macro columns — VERIFIED monthly, cover 2005:**
  | Column | FRED ID | Source | Note |
  |--------|---------|--------|------|
  | `exchange_rate_twd_usd` | `EXTAUS` | Fed G.5 | TWD/USD spot |
  | `real_broad_eer` | `RBTWBIS` | BIS | from 1994 |
  | `nominal_broad_eer` | `NBTWBIS` | BIS | nominal vs real contrast |
  | `total_reserves` | `TRESEGTWM194N` | IMF IFS | millions of SDR |
  | `real_narrow_eer` *(optional)* | `RNTWBIS` | BIS | redundant w/ RBTWBIS |
  | `nominal_narrow_eer` *(optional)* | `NNTWBIS` | BIS | redundant w/ NBTWBIS |
- **dim_macro — FINAL (locked):** 4 columns → `EXTAUS`, `RBTWBIS`, `NBTWBIS`, `TRESEGTWM194N`. FRED-only (FX + reserves), no interest rate. The 4 BIS effective-exchange-rate variants are highly correlated; the narrow ones (`RNTWBIS`, `NNTWBIS`) are optional extras only.
- **Column-count note:** the ≥12-column requirement (brief §4) is already satisfied by the credit data (24 cols) + ≥5 engineered features. Macro columns are **enrichment**, not needed to reach 12.

### Multi-source / Multi-format compliance (brief §4)
- Two sources ✅ (UCI file + FRED API). Two formats ✅ (XLSX/CSV + JSON) → bonus.

### Join Strategy — **CONFIRMED: Option (c) + monthly grain (unpivot)**
- Unpivot each credit client into **6 monthly rows (Apr–Sep 2005)** → fact grain = **client × billing month**.
- Each monthly row links to `dim_date` (the 12 months of 2005), which links to the monthly macro table.
- Macro and credit are related through `dim_date`.

### Synthetic Augmentation — **CTGAN (DONE ✅)**
- **Generated:** 150,000 synthetic credit clients, default balance {non-default 0.7788, default 0.2212} — original ~22% ratio preserved via conditional sampling. Seed 42.
- Output: `raw/synthetic_credit_clients.csv` = **credit source 1** for all pipeline stages.
- **CTGAN is a one-time pre-step** — it OOM-kills Hive if run alongside the stack (torch peaks ~6.4 GB). Run it once with Hive stopped, copy output to `raw/`, then the standard pipeline skips CTGAN entirely.
- Library: SDV `CTGANSynthesizer`. Script: `synthetic/train_ctgan.py`.
- **Row-count result:** 150k clients × 6 months unpivot = **900,000 fact rows** (≫ 100k minimum). ✅
- Report must document: method, rationale for CTGAN, potential bias/limitations.

---

## 4. Repository Structure (required deliverable)

```
bigdata_final_project/
├── etl_pipeline/        # extract.py (extract_etl_source1/2), transform.py, load.py, logs/
├── elt_pipeline/        # extract_load.py, transform.sql / .py, logs/
├── raw/                 # raw extracted data (untouched)
├── datalake/            # raw landing zone for ELT
├── warehouse/           # Hive schema DDL + analytical query files
├── dashboard/           # Tableau (.twb/.twbx, ETL) + Power BI (.pbix, ELT) + screenshots
├── synthetic/           # CTGAN training + generation scripts
├── architecture_diagram.pdf
└── report.pdf
```

---

## 5. Architecture (data flow)

```
Sources (UCI XLSX/CSV  +  FRED API/JSON, 2005)
        │
        ▼
   Kafka producers ──► Kafka topics ──► consumers
        │                                   │
        ├──────────────► raw/  (ETL path)   └──► datalake/ (ELT path)
        │                                                │
   [ETL] Spark transform (PySpark)                [ELT] load raw → Hive raw tables
   (clean/std/unpivot→monthly/enrich/validate)          │
        │                                          Hive / Spark SQL transform
        ▼                                          (window funcs, OLAP aggregation)
   Hive warehouse — ETL star schema                     ▼
   (fact_credit_monthly + dims + dim_macro)       Hive warehouse — ELT tables
        │                                                │
        ▼                                                ▼
     Tableau  (Hive ODBC)                           Power BI  (Hive ODBC)
            └────────── same dashboard design ──────────┘
```

Export the diagram as `architecture_diagram.pdf`.

---

## 6. Part I — ETL Pipeline (weight 30%)

### 6.1 Extract
- `extract_etl_source1()` — UCI credit card (zip→xls, fallback ucimlrepo CSV); `extract_etl_source2()` — FRED API (**4** monthly series: `EXTAUS`, `RBTWBIS`, `NBTWBIS`, `TRESEGTWM194N`).
- **Active credit source 1 = `raw/synthetic_credit_clients.csv`** (CTGAN output, pre-generated). The UCI xls is still extracted and kept as provenance but the pipeline reads the synthetic file.
- Persist raw to `raw/`; **no cleaning/transform here**.
- Log per source: source name, row & column count, file/data size, extract execution time.

### 6.2 Transform (highest difficulty)
**a. Cleaning:** drop duplicates by PK; handle missing values by dtype; standardize date/time. **Outlier detection — CONFIRMED:** Credit Card → **IQR**; FRED macro → **Z-Score**.
**b. Standardization:** column names → `lowercase snake_case`; **normalize ≥2 numeric columns — CONFIRMED set:** `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` (re-mapped from the original CPI/Interest/Unemployment plan, since those are not monthly on FRED for Taiwan). Encode categoricals; enforce dtype consistency.
**c. Enrichment & Feature Engineering:** unpivot to monthly; join macro via `dim_date`; create **≥5 features** — CONFIRMED:
  - `credit_utilization = bill_amt / limit_bal`
  - `payment_ratio = pay_amt / bill_amt`
  - `avg_delay_months` (mean of PAY_* statuses)
  - `num_months_delayed` (count of positive delays)
  - `repayment_gap` (total_bill − total_payment)
  - (+ macro-joined columns per month)
**d. Validation — ≥6 rules:** uniqueness, null, range, datatype consistency, referential integrity, distribution. Failed rules → fix + document.

### 6.3 Load
- Load to Hive warehouse. **Star schema (CONFIRMED — monthly grain):**
  - `fact_credit_monthly` — grain: one row per **client × month** (Apr–Sep 2005); measures: bill_amt, pay_amt, pay_status, engineered features; FKs to `dim_client`, `dim_date`.
  - `dim_client` — demographics (sex, education, marriage, age band).
  - `dim_date` — 2005 monthly calendar; bridges credit ↔ macro.
  - `dim_macro` — monthly Taiwan macro indicators (4 series cols + date_key), linked via `dim_date`.
- Documented PK/FK. Run **≥8 analytical SQL queries**. Log Load status + execution time.

---

## 7. Part II — ELT Pipeline (weight 30%)

- **Extract + Load:** pull same raw sources (no preprocessing) → `datalake/` / Hive raw tables; document metadata (size, structure).
- **Transform (in-warehouse) — CONFIRMED differentiation:**
  - **ETL** = Python row-level cleaning + unpivot + ML-oriented features (Spark DataFrame API).
  - **ELT** = set-based SQL in Hive: **window functions, OLAP-style aggregations**, materialized analytical tables.
- Must be a genuinely different approach — not a copy of ETL output.

---

## 8. Part III — Dashboard (weight 25%)

- **Same dashboard design built in both Tableau and Power BI.**
  - **Tableau** → ETL warehouse output; **Power BI** → ELT warehouse output; both via **Hive ODBC**.
- Required: KPIs; time-based trend analysis; distribution & comparison; interactive filters.
- **KPIs — CONFIRMED:**
  - Overall default rate.
  - Default rate per demographic (sex / education / marriage / age band).
  - Correlation of default vs macro indicators (exchange rate / effective exch. rate / reserves over Apr–Sep 2005). NB: no monthly interest rate available for Taiwan on FRED.

---

## 9. ETL vs ELT Comparative Analysis (report, weight 15%)
From real experiments: runtime per stage, resource usage, code complexity, flexibility, where the transform load sits, data freshness, suitability. Bonus: compare the Tableau (ETL) vs Power BI (ELT) dashboards.

---

## 10. Dataset Spec Compliance Checklist (brief §4)
- [x] ≥100,000 rows — **900,000 monthly fact rows** (150k clients × 6 months) ✅
- [x] ≥12 columns (24 credit + ≥5 engineered + 4 macro enrichment cols)
- [x] ≥2 sources (UCI + FRED API)
- [x] ≥2 formats (XLSX/CSV + JSON) — bonus
- [x] numeric + categorical + datetime columns
- [x] missing values present & handled
- [x] duplicate rows present & handled
- [x] ≥1 ID column as PK/FK
- [x] synthetic method documented in `docs/PROSES_ETL_ELT.pdf` (§A2) and `docs/DOKUMENTASI_LENGKAP.pdf`

---

## 11. Conventions & Rules
- Python: PEP 8, `snake_case`, type hints, docstrings on pipeline functions.
- All column names `lowercase snake_case` after standardization.
- Every stage emits a structured log (stage, source, rows, cols, size, duration, status).
- **Reproducibility:** runnable end-to-end; pin versions; seed CTGAN; document run order in README.
- No hardcoded secrets — `.env` for FRED API key.
- Every design decision explained in the report (brief §11). No plagiarism.

## 12. Grading Weights
ETL 30% · ELT 30% · Dashboard 25% · Analysis & Report 15%.

---

## 13. Remaining Open Items
1. **VERIFIED ✅** FRED macro series confirmed monthly & covering 2005: `EXTAUS`, `RBTWBIS`, `NBTWBIS`, `TRESEGTWM194N`. No monthly interest rate / CPI / unemployment for Taiwan on FRED.
2. **TODO:** Author `report.pdf` (pipeline comparison §9, discussion of zero macro correlation — see §14). `architecture_diagram.pdf` generated by `architecture_diagram.py`.
3. **TODO:** Build Tableau (.twbx) and Power BI (.pbix) dashboard files in `dashboard/`. ODBC DSN settings verified (§14).

---

## 14. Operational Notes (from real runs — 2026-06-10)

### Verified run results
| Metric | Value |
|--------|-------|
| Synthetic clients | 150,000 (default rate 0.2212) |
| ETL fact rows | 900,000 (150k × 6 months) |
| ETL validation | 6/6 PASS |
| ETL runtime | ~79.3 s (transform 59 s + load) |
| ELT runtime | ~22.6 s (~3.5× faster — set-based SQL) |
| Peak RSS ETL | ~95.8 MB |
| Peak RSS ELT | ~80.5 MB |
| Overall default rate | **0.2212** |
| Default by sex | female 0.2439 > male 0.1991 |
| Default by education | grad-school 0.237 > university 0.161 |
| Default by marriage | married 0.2661 > single |
| Default ↔ macro corr | **≈0.0** (see note below) |

> **Zero correlation note:** `default_payment_next_month` is a client-level constant denormalised across 6 monthly rows → zero monthly variance → zero correlation with macro. Document this grain limitation in the report. A time-varying default label would be needed for meaningful macro linkage.

### Docker / environment fixes (all already in code)
- Base image: `bitnamilegacy/spark:3.5` (bitnami free catalog removed 2025)
- Skip `pyspark` reinstall in `Dockerfile.spark` (saves 317 MB + avoids OOM)
- `/etc/passwd` entry for uid 1001 → fixes torch `getpass` + JVM `user.home`/ivy
- Hive Postgres JDBC via `COPY` on host (not `ADD <url>` which produced a 0-byte file)
- Warehouse-writing Spark stages run with `docker compose exec -u root` (uid 1000 Hive vs uid 1001 Spark clash on shared volume)
- `DROP DATABASE … CASCADE` in load/ELT scripts → idempotent re-runs
- All KPI/ELT CTAS use `USING PARQUET` → Hive/ODBC-readable
- Stop `spark-worker kafka kafka-ui` before connecting BI tools — HiveServer2 needs the RAM headroom

### Power BI ODBC connection (fix for "Unexpected response received from server")
- ODBC Data Sources (64-bit) → System DSN → Configure:
  - Host `localhost`, Port `10000`
  - Database: `bigdata_elt` (Power BI) / `bigdata_etl` (Tableau)
  - Hive Server Type: **HiveServer2**, Mechanism: **User Name**, User: `hive`
  - **Thrift Transport = Binary** ← critical fix; SSL = OFF
  - Test → SUCCESS
- Power BI: Get Data → ODBC → [DSN] → Connect → load `kpi_*` tables
- CSV fallback: `beeline … --outputformat=csv2` then Get Data → Text/CSV

### Generated docs (in `docs/`)
| File | Description |
|------|-------------|
| `DOKUMENTASI_LENGKAP.pdf` | Complete bilingual component reference |
| `PROSES_ETL_ELT.pdf` | Bilingual ETL & ELT process walkthrough with real numbers |
| `CARA_MENJALANKAN.pdf` | Bilingual start-to-finish run guide (all fixes included) |

Regenerate PDFs: `python docs/build_pdfs.py` (uses Edge headless → xhtml2pdf fallback).
