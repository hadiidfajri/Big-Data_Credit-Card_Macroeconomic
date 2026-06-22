# Tugas Besar Big Data — ETL & ELT Pipeline + Analytics Dashboard

Credit-card **default-risk analytics for Taiwan (2005)**, relating borrower behaviour to the
macroeconomic environment (FRED Taiwan series). 

Pipeline lengkap: **Extract (Kafka) → ETL (PySpark) / ELT (Hive SQL) → Hive warehouse → Dashboard
(web, self-contained)**, di atas **Docker Compose**. Hasil run nyata: **150.000 nasabah sintetis (CTGAN)
→ 900.000 baris fakta bulanan**, default rate **0,2212**.

---

## Pemenuhan Syarat Pengumpulan

| # | Syarat | Lokasi di repo |
|---|--------|----------------|
| 1 | Pipeline ETL & ELT | **ETL:** [etl_pipeline/extract.py](etl_pipeline/extract.py), [transform.py](etl_pipeline/transform.py), [load.py](etl_pipeline/load.py) · **ELT:** [elt_pipeline/extract_load.py](elt_pipeline/extract_load.py), [transform.sql](elt_pipeline/transform.sql), [run_transform.py](elt_pipeline/run_transform.py) · proses ber-gambar: [docs/PROSES_ETL_ELT.pdf](docs/PROSES_ETL_ELT.pdf). *(Catatan: pipeline berupa script `.py`/`.sql` dijalankan via Docker — notebook Colab belum disertakan.)* |
| 2 | Dokumentasi warehouse | **Schema/ERD:** [warehouse/erd_star_schema.png](warehouse/erd_star_schema.png), [warehouse/elt_lineage.png](warehouse/elt_lineage.png), [docs/ERD_DATABASE.pdf](docs/ERD_DATABASE.pdf) · **Struktur tabel (DDL):** [warehouse/etl_star_schema.sql](warehouse/etl_star_schema.sql) · **Query SQL analitik:** [warehouse/etl_analytical_queries.sql](warehouse/etl_analytical_queries.sql) |
| 3 | Dashboard | **Web dashboard (self-contained):** [dashboard/web/index.html](dashboard/web/index.html) ([preview](dashboard/web/preview.png)) — buka langsung di browser |
| 4 | Dokumentasi dataset | Bagian **Datasets** di bawah [docs/DOKUMENTASI_LENGKAP.pdf](docs/DOKUMENTASI_LENGKAP.pdf) |
| 5 | Script pengambilan data (API) | [etl_pipeline/extract.py](etl_pipeline/extract.py) (`extract_etl_source2` = FRED API JSON; `extract_etl_source1` = UCI) + penjelasan di [docs/PROSES_ETL_ELT.pdf](docs/PROSES_ETL_ELT.pdf) §A1 |
| 6 | Laporan paper | [report.pdf](report.pdf) (sumber: [report/report.md](report/report.md)) |
| 7 | architecture_diagram.png | [architecture_diagram.png](architecture_diagram.png) |
| 8 | README.md | berkas ini |

### Datasets
- **Sumber 1 — UCI Default of Credit Card Clients (id 350)**, format XLSX/CSV, ~30.000×24 →
  <https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients>. Data perilaku
  pembayaran/tagihan nasabah kartu kredit Taiwan (Apr–Sep 2005). Diperbanyak ke 150.000 via CTGAN.
- **Sumber 2 — FRED (Federal Reserve Economic Data), seri Taiwan**, format **API JSON**, 2005 →
  <https://fred.stlouisfed.org/categories/32438>. Seri: `EXTAUS`, `RBTWBIS`, `NBTWBIS`,
  `TRESEGTWM194N` (kurs + cadangan devisa).
- Multi-source ✅ (UCI + FRED) · multi-format ✅ (XLSX/CSV + JSON, bonus).
- Dataset besar **tidak** di-commit: file mentah `raw/` & FRED JSON di-`.gitignore`; CSV sintetis
  (14 MB) disertakan untuk reprodusibilitas.

---

## Repository layout

```
.
├── common/              # shared: paths, logging, metrics (instrumentation), Spark session
├── etl_pipeline/        # extract.py, kafka_producer/consumer.py, transform.py, load.py, logs/ (Part I)
├── elt_pipeline/        # extract_load.py, transform.sql, run_transform.py, logs/  (Part II)
├── synthetic/           # train_ctgan.py + CTGAN_METHOD.md  (≥150k synthetic clients)
├── raw/                 # raw extracted data for the ETL path (untouched)
├── datalake/            # raw landing zone for the ELT path
├── warehouse/           # star-schema DDL, 8 analytical queries, dashboard_kpis.sql, staging/
├── dashboard/           # build_dashboard_kpis.py, HIVE_ODBC_CONNECTION.md, DASHBOARD_SPEC.md, screenshots/
├── analysis/            # compare_pipelines.py + ETL_vs_ELT_comparison.md  (Part of §9)
├── report/              # report.md skeleton (-> report.pdf)
├── logs/                # pipeline_metrics.jsonl (cross-cutting, for the ETL-vs-ELT comparison)
├── docker/              # Dockerfile.spark, Dockerfile.hive (infra build files)
├── architecture_diagram.py / .pdf / .png   # data-flow diagram 
├── docker-compose.yml   # Kafka (KRaft) + Spark cluster + Hive warehouse
├── requirements.txt     # pinned Python deps (baked into the Spark image)
└── .env.example         # environment template (FRED_API_KEY + infra config)
```

---

## Prerequisites

- **Docker Desktop** (with the WSL2 backend on Windows 11) — provides `docker compose`.
- A free **FRED API key** — https://fred.stlouisfed.org/docs/api/api_key.html
- A modern **web browser** — the dashboard ([dashboard/web/index.html](dashboard/web/index.html)) is fully
  self-contained (no server, ODBC, or internet) and covers **both ETL and ELT** via an in-page toggle.
- *(Optional)* local **Python 3.11** if you want to run scripts outside the containers.

---

## Setup

```powershell
# 1. Create your env file and add the FRED key
Copy-Item .env.example .env
#    then edit .env -> set FRED_API_KEY=...

# 2. Build the custom Spark + Hive images (installs requirements.txt, adds the Postgres JDBC driver)
docker compose build

# 3. Start the whole stack
docker compose up -d

# 4. Check status
docker compose ps
```

### Services & ports

| Service          | URL / endpoint                  | Purpose                                   |
|------------------|---------------------------------|-------------------------------------------|
| Kafka (broker)   | `localhost:9092`                | extract-stage message bus (KRaft, no ZK)  |
| Kafka UI         | http://localhost:8085           | inspect topics / messages (optional)      |
| Spark master UI  | http://localhost:8080           | cluster status — should show **1 worker** |
| Spark master     | `spark://localhost:7077`        | submit jobs to the cluster                |
| Hive metastore   | `thrift://localhost:9083`       | table metadata (Spark connects here)      |
| HiveServer2      | `localhost:10000`               | JDBC/ODBC endpoint (beeline / ad-hoc SQL)  |
| HiveServer2 UI   | http://localhost:10002          | query / session monitoring                |
| Postgres         | internal                        | Hive metastore backing DB                 |

> In-container clients reach Kafka at `kafka:19092` (not `localhost:9092`). Spark and Hive share the
> `warehouse` volume mounted at the **same path** (`/opt/hive/data/warehouse`) in every container, so
> the absolute table paths stored in the metastore resolve from the Spark containers too.

### Smoke tests

```powershell
# Hive reachable?
docker compose exec hiveserver2 beeline -u "jdbc:hive2://localhost:10000" -e "SHOW DATABASES;"

# Kafka reachable? (create + list a topic)
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic smoke-test
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

---

## Run order (full pipeline)

```
                 EXTRACT                    TRANSFORM                         LOAD
ETL  (Part I) :  extract.py  ──►  transform.py ──► load.py ──► 8 analytical queries
                 (UCI + FRED -> raw/)   (≥150k clients, before FRED merge)   (Hive star schema)
ELT  (Part II):  extract_load.py ──────────────────────►  transform.sql (in-warehouse, window/OLAP)
                 (same sources -> datalake/ -> Hive raw tables)
```

All stages run inside the Spark image (deps baked in; service-name config already set there):

```powershell
# 0. (optional) Kafka smoke test — see the streaming Extract path end-to-end
docker compose exec spark-master python /app/etl_pipeline/kafka_consumer.py --idle-ms 8000   # terminal A
docker compose exec spark-master python /app/etl_pipeline/kafka_producer.py --limit 50       # terminal B

# 1. Extract raw sources -> raw/   (FRED needs FRED_API_KEY in .env)
docker compose exec spark-master python /app/etl_pipeline/extract.py

# 2. CTGAN — ONE-TIME pre-step (heavy; OOMs Hive if run together). Run it ONCE, then
#    copy its output to raw/ as credit "source 1" and SKIP it on subsequent runs:
#    docker compose stop hive-metastore hiveserver2   # free memory while CTGAN trains
#    docker compose exec spark-master python /app/synthetic/train_ctgan.py --n 150000 --seed 42
#    Copy-Item synthetic/synthetic_credit_clients.csv raw/   # -> raw/synthetic_credit_clients.csv
#    docker compose start hive-metastore hiveserver2
# (Standard runs read raw/synthetic_credit_clients.csv directly — no CTGAN needed.)

# 3. ETL: transform (PySpark) then load (Hive star schema + 8 queries)
docker compose exec spark-master spark-submit /app/etl_pipeline/transform.py
docker compose exec spark-master spark-submit /app/etl_pipeline/load.py

# 4. ELT: land raw into Hive, then in-warehouse SQL (window/OLAP)
docker compose exec spark-master spark-submit /app/elt_pipeline/extract_load.py
docker compose exec spark-master spark-submit /app/elt_pipeline/run_transform.py

# 5. Build dashboard KPI tables (kpi_* in both bigdata_etl and bigdata_elt)
docker compose exec spark-master spark-submit /app/dashboard/build_dashboard_kpis.py

# 6. ETL-vs-ELT comparison (reads logs/pipeline_metrics.jsonl) + architecture diagram
docker compose exec spark-master python /app/analysis/compare_pipelines.py
python architecture_diagram.py    # diagram renders fine on the host (matplotlib)
```

> Jobs default to `--master local[*]` . To use the cluster instead, set
> `APP_SPARK_MASTER=spark://spark-master:7077` in the `spark-master` service env.
> Local (non-Docker) runs also work if you `pip install -r requirements.txt` first; `.env`'s
> `localhost` addresses are then used automatically.

---

## Dashboard

Visualization is **web-only** — no Power BI, no Tableau. A single fully **self-contained** page at
[dashboard/web/index.html](dashboard/web/index.html) is the dashboard: no web server, no ODBC, no internet,
just open it in a browser. It embeds the KPI CSVs and has an **ETL/ELT toggle** covering **both** warehouse
outputs (`bigdata_etl` / `bigdata_elt`) in one view — the two pipelines produce identical KPIs, itself
evidence they agree. Static render: [dashboard/web/preview.png](dashboard/web/preview.png).

Design spec: [dashboard/DASHBOARD_SPEC.md](dashboard/DASHBOARD_SPEC.md) /
[dashboard/DASHBOARD_BUILD_GUIDE.md](dashboard/DASHBOARD_BUILD_GUIDE.md) (4 zones). Regenerate the page:
`python dashboard/export_kpis_csv.py && python dashboard/build_web_dashboard.py` (see
[dashboard/web/README.md](dashboard/web/README.md)).

---

## Documentation & deliverables

| Artefak | Lokasi |
|---|---|
| Laporan paper (PDF) | [report.pdf](report.pdf) (sumber: [report/report.md](report/report.md)) — render ulang: `python report/build_report_pdf.py` |
| Architecture diagram | [architecture_diagram.png](architecture_diagram.png) — `python architecture_diagram.py` |
| ERD / star schema | [warehouse/erd_star_schema.png](warehouse/erd_star_schema.png) — `python warehouse/erd_diagram.py` |
| Schema DDL + 8 query analitik | [warehouse/etl_star_schema.sql](warehouse/etl_star_schema.sql), [warehouse/etl_analytical_queries.sql](warehouse/etl_analytical_queries.sql) |

---

## Teardown

```powershell
docker compose down        # stop & remove containers (keeps data volumes)
docker compose down -v     # also wipe Kafka / Postgres / warehouse volumes (fresh start)
```

---

## Caveats / known frictions  (all verified during a real end-to-end run)

1. **Spark base image = `apache/spark:3.5.3-python3`.** Bitnami retired the free `bitnami/spark`
   catalog in 2025 and never shipped arm64, so `docker/Dockerfile.spark` now uses the official
   multi-arch `apache/spark` (works on local amd64 **and** the Oracle Cloud ARM VM). Because the
   apache base has no bitnami `SPARK_MODE` entrypoint, the master/worker start commands are set
   explicitly in `docker-compose.yml`.
2. **uid 1001 needs a passwd entry.** `Dockerfile.spark` adds `sparkuser` to `/etc/passwd`; without it
   torch's `getpass.getuser()` crashes CTGAN and the JVM's `user.home='?'` breaks Spark ivy
   (`basedir must be absolute`). `HOME=/tmp` + `spark.jars.ivy=/tmp/.ivy2` are also set.
3. **`pyspark` is NOT pip-installed** in the Spark image (the base ships it) — saves ~600 MB and avoids a
   build OOM on the 317 MB sdist.
4. **Postgres JDBC for the metastore is COPY'd, not ADD'd.** `ADD <url>` produced a 0-byte jar
   (Maven redirect) → `ClassNotFoundException`. `docker/postgresql-42.7.4.jar` is fetched on the host
   and copied in (`Dockerfile.hive`).
5. **Warehouse volume permissions.** Spark (uid 1001) writes all data; the metastore creates DB dirs as
   its own uid. After first `up`, make the shared volume writable once:
   `docker run --rm --user 0 --entrypoint sh -v bigdata-tubes_warehouse:/wh bigdata-spark:3.5 -c "chmod -R 777 /wh"`.
   Also `spark.sql.legacy.createHiveTableByDefault=false` makes CTAS use Spark's native parquet writer
   (no `.hive-staging` in metastore-owned dirs).
6. **Memory / OOM.** The whole stack + CTGAN's torch (~6 GB) can exceed a default ~7.5 GB Docker VM and
   the kernel OOM-kills the Hive JVMs (exit 137). Give Docker Desktop ≥10–12 GB (Settings → Resources,
   or `.wslconfig`), or run CTGAN with the Hive services stopped.
7. **HiveServer2 stale PID.** After an unclean exit, HS2 refuses to restart ("running as process 7.
   Stop it first."). Fix with `docker compose up -d --force-recreate hiveserver2`.
8. **Hive 4.0 ↔ Spark 3.5 metastore client.** Works for DDL/DML over Thrift; `ALTER TABLE … ADD
   CONSTRAINT` (PK/FK) is rejected by the bundled Hive 2.3.9 client, so constraints stay documented in
   `warehouse/etl_star_schema.sql` (informational only — load.py logs them as skipped).
9. **Docker on a full C: drive.** The WSL VM disk lives on C:; if C: is near-full the daemon wedges
   mid-build. Free space or move Docker's disk image to a roomier drive.
