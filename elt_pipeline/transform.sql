-- ============================================================================
-- ELT in-warehouse transform (CLAUDE.md §7) — set-based HiveQL / Spark SQL.
-- Deliberately DIFFERENT from the ETL approach: no Python row logic. Everything
-- here is SQL — an in-SQL unpivot (stack), WINDOW functions, and OLAP GROUPING
-- SETS — producing materialised analytical tables. Executed by run_transform.py.
-- Database: bigdata_elt   (raw_credit, raw_macro produced by extract_load.py)
-- ============================================================================

-- 1) Macro: pivot the long raw_macro into one row per month (SQL CASE pivot) ---
CREATE TABLE IF NOT EXISTS bigdata_elt.elt_macro_monthly USING PARQUET AS
SELECT
  CAST(substr(obs_date, 1, 4) AS INT) * 100 + CAST(substr(obs_date, 6, 2) AS INT) AS date_key,
  MAX(CASE WHEN series_id = 'EXTAUS'        THEN CAST(value AS DOUBLE) END) AS exchange_rate_twd_usd,
  MAX(CASE WHEN series_id = 'RBTWBIS'       THEN CAST(value AS DOUBLE) END) AS real_broad_eer,
  MAX(CASE WHEN series_id = 'NBTWBIS'       THEN CAST(value AS DOUBLE) END) AS nominal_broad_eer,
  MAX(CASE WHEN series_id = 'TRESEGTWM194N' THEN CAST(value AS DOUBLE) END) AS total_reserves
FROM bigdata_elt.raw_macro
WHERE value IS NOT NULL AND value <> '.'
GROUP BY CAST(substr(obs_date, 1, 4) AS INT) * 100 + CAST(substr(obs_date, 6, 2) AS INT);

-- 2) Monthly fact: unpivot the 6 billing months IN SQL via stack() -------------
CREATE TABLE IF NOT EXISTS bigdata_elt.elt_fact_monthly USING PARQUET AS
SELECT
  c.id,
  m.date_key,
  c.limit_bal,
  m.pay_status,
  m.bill_amt,
  m.pay_amt,
  c.default_payment_next_month,
  ROUND(m.bill_amt / NULLIF(c.limit_bal, 0), 4) AS credit_utilization,
  ROUND(m.pay_amt  / NULLIF(m.bill_amt, 0), 4)  AS payment_ratio
FROM bigdata_elt.raw_credit c
LATERAL VIEW stack(6,
  200509, c.pay_0, c.bill_amt1, c.pay_amt1,
  200508, c.pay_2, c.bill_amt2, c.pay_amt2,
  200507, c.pay_3, c.bill_amt3, c.pay_amt3,
  200506, c.pay_4, c.bill_amt4, c.pay_amt4,
  200505, c.pay_5, c.bill_amt5, c.pay_amt5,
  200504, c.pay_6, c.bill_amt6, c.pay_amt6
) m AS date_key, pay_status, bill_amt, pay_amt;

-- 3) WINDOW functions: per-client month-over-month trends & in-month ranking ---
CREATE TABLE IF NOT EXISTS bigdata_elt.elt_client_trends USING PARQUET AS
SELECT
  id,
  date_key,
  bill_amt,
  pay_amt,
  credit_utilization,
  LAG(bill_amt) OVER (PARTITION BY id ORDER BY date_key) AS prev_bill_amt,
  bill_amt - LAG(bill_amt) OVER (PARTITION BY id ORDER BY date_key) AS bill_mom_change,
  ROUND(AVG(credit_utilization) OVER (
      PARTITION BY id ORDER BY date_key
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 4) AS run_avg_utilization,
  RANK() OVER (PARTITION BY date_key ORDER BY bill_amt DESC) AS bill_rank_in_month
FROM bigdata_elt.elt_fact_monthly;

-- 4) OLAP: default rate per demographic via GROUPING SETS (incl. grand total) --
CREATE TABLE IF NOT EXISTS bigdata_elt.elt_default_by_demographic USING PARQUET AS
SELECT
  sex_label, education_label, marriage_label, age_band,
  COUNT(*)                       AS clients,
  ROUND(AVG(is_default), 4)      AS default_rate
FROM (
  SELECT
    CASE WHEN sex = 1 THEN 'male' WHEN sex = 2 THEN 'female' ELSE 'unknown' END AS sex_label,
    CASE WHEN education = 1 THEN 'graduate_school'
         WHEN education = 2 THEN 'university'
         WHEN education = 3 THEN 'high_school'
         WHEN education = 4 THEN 'others' ELSE 'unknown' END                    AS education_label,
    CASE WHEN marriage = 1 THEN 'married'
         WHEN marriage = 2 THEN 'single'
         WHEN marriage = 3 THEN 'others' ELSE 'unknown' END                     AS marriage_label,
    CASE WHEN age < 30 THEN '<30' WHEN age < 40 THEN '30-39'
         WHEN age < 50 THEN '40-49' WHEN age < 60 THEN '50-59' ELSE '60+' END   AS age_band,
    default_payment_next_month AS is_default
  FROM bigdata_elt.raw_credit
) t
GROUP BY sex_label, education_label, marriage_label, age_band
GROUPING SETS ((sex_label), (education_label), (marriage_label), (age_band), ());

-- 5) Default rate aligned with macro per month (for the macro-correlation KPI) -
CREATE TABLE IF NOT EXISTS bigdata_elt.elt_default_vs_macro USING PARQUET AS
SELECT
  f.date_key,
  ROUND(AVG(f.default_payment_next_month), 4) AS default_rate,
  MAX(mm.exchange_rate_twd_usd)               AS exchange_rate_twd_usd,
  MAX(mm.real_broad_eer)                      AS real_broad_eer,
  MAX(mm.total_reserves)                      AS total_reserves
FROM bigdata_elt.elt_fact_monthly f
LEFT JOIN bigdata_elt.elt_macro_monthly mm ON f.date_key = mm.date_key
GROUP BY f.date_key
ORDER BY f.date_key;
