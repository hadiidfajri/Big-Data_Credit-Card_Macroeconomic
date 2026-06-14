-- ============================================================================
-- Dashboard KPI layer (CLAUDE.md §8). Materialised aggregate TABLES (not views)
-- so they are fully Hive/ODBC-readable by Tableau & Power BI.
--
-- IDENTICAL kpi_* table names exist in BOTH databases so the same dashboard
-- design binds to either warehouse:
--   bigdata_etl.kpi_*  -> Tableau   (ETL output)
--   bigdata_elt.kpi_*  -> Power BI   (ELT output)
--
-- Run via Spark (Hive-readable parquet output):
--   docker compose exec spark-master spark-submit /app/dashboard/build_dashboard_kpis.py
-- ============================================================================

-- ========================== ETL  (bigdata_etl -> Tableau) ===================
DROP TABLE IF EXISTS bigdata_etl.kpi_overall;
CREATE TABLE bigdata_etl.kpi_overall USING PARQUET AS
SELECT ROUND(AVG(default_payment_next_month), 4) AS default_rate,
       COUNT(*)                                  AS total_clients
FROM bigdata_etl.dim_client;

DROP TABLE IF EXISTS bigdata_etl.kpi_default_by_demographic;
CREATE TABLE bigdata_etl.kpi_default_by_demographic USING PARQUET AS
SELECT 'sex' AS dimension, sex_label AS category, COUNT(*) AS clients,
       ROUND(AVG(default_payment_next_month), 4) AS default_rate
FROM bigdata_etl.dim_client GROUP BY sex_label
UNION ALL
SELECT 'education', education_label, COUNT(*),
       ROUND(AVG(default_payment_next_month), 4)
FROM bigdata_etl.dim_client GROUP BY education_label
UNION ALL
SELECT 'marriage', marriage_label, COUNT(*),
       ROUND(AVG(default_payment_next_month), 4)
FROM bigdata_etl.dim_client GROUP BY marriage_label
UNION ALL
SELECT 'age_band', age_band, COUNT(*),
       ROUND(AVG(default_payment_next_month), 4)
FROM bigdata_etl.dim_client GROUP BY age_band;

DROP TABLE IF EXISTS bigdata_etl.kpi_monthly_default_vs_macro;
CREATE TABLE bigdata_etl.kpi_monthly_default_vs_macro USING PARQUET AS
SELECT d.date_key, d.month_name,
       ROUND(AVG(f.default_payment_next_month), 4) AS default_rate,
       ROUND(AVG(f.exchange_rate_twd_usd), 4)      AS exchange_rate_twd_usd,
       ROUND(AVG(f.real_broad_eer), 4)             AS real_broad_eer,
       ROUND(AVG(f.total_reserves), 2)             AS total_reserves
FROM bigdata_etl.fact_credit_monthly f
JOIN bigdata_etl.dim_date d ON f.date_key = d.date_key
GROUP BY d.date_key, d.month_name
ORDER BY d.date_key;

DROP TABLE IF EXISTS bigdata_etl.kpi_corr_default_macro;
CREATE TABLE bigdata_etl.kpi_corr_default_macro USING PARQUET AS
SELECT ROUND(CORR(default_payment_next_month, exchange_rate_twd_usd), 4) AS corr_fx,
       ROUND(CORR(default_payment_next_month, real_broad_eer), 4)        AS corr_reer,
       ROUND(CORR(default_payment_next_month, total_reserves), 4)        AS corr_reserves
FROM bigdata_etl.fact_credit_monthly;

-- ========================== ELT  (bigdata_elt -> Power BI) ===================
DROP TABLE IF EXISTS bigdata_elt.kpi_overall;
CREATE TABLE bigdata_elt.kpi_overall USING PARQUET AS
SELECT default_rate, clients AS total_clients
FROM bigdata_elt.elt_default_by_demographic
WHERE sex_label IS NULL AND education_label IS NULL
  AND marriage_label IS NULL AND age_band IS NULL;

DROP TABLE IF EXISTS bigdata_elt.kpi_default_by_demographic;
CREATE TABLE bigdata_elt.kpi_default_by_demographic USING PARQUET AS
SELECT 'sex' AS dimension, sex_label AS category, clients, default_rate
FROM bigdata_elt.elt_default_by_demographic WHERE sex_label IS NOT NULL
UNION ALL
SELECT 'education', education_label, clients, default_rate
FROM bigdata_elt.elt_default_by_demographic WHERE education_label IS NOT NULL
UNION ALL
SELECT 'marriage', marriage_label, clients, default_rate
FROM bigdata_elt.elt_default_by_demographic WHERE marriage_label IS NOT NULL
UNION ALL
SELECT 'age_band', age_band, clients, default_rate
FROM bigdata_elt.elt_default_by_demographic WHERE age_band IS NOT NULL;

DROP TABLE IF EXISTS bigdata_elt.kpi_monthly_default_vs_macro;
CREATE TABLE bigdata_elt.kpi_monthly_default_vs_macro USING PARQUET AS
SELECT v.date_key,
       CASE v.date_key % 100
            WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Apr'
            WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug'
            WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dec' END AS month_name,
       v.default_rate, v.exchange_rate_twd_usd, v.real_broad_eer, v.total_reserves
FROM bigdata_elt.elt_default_vs_macro v
ORDER BY v.date_key;

DROP TABLE IF EXISTS bigdata_elt.kpi_corr_default_macro;
CREATE TABLE bigdata_elt.kpi_corr_default_macro USING PARQUET AS
SELECT ROUND(CORR(f.default_payment_next_month, mm.exchange_rate_twd_usd), 4) AS corr_fx,
       ROUND(CORR(f.default_payment_next_month, mm.real_broad_eer), 4)        AS corr_reer,
       ROUND(CORR(f.default_payment_next_month, mm.total_reserves), 4)        AS corr_reserves
FROM bigdata_elt.elt_fact_monthly f
JOIN bigdata_elt.elt_macro_monthly mm ON f.date_key = mm.date_key;
