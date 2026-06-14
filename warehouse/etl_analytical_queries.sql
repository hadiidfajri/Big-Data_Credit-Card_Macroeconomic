-- ============================================================================
-- ETL warehouse — 8 analytical queries (CLAUDE.md §6.3). Run by load.py.
-- Statements are split on ';' and executed in order; '--' lines are ignored.
-- ============================================================================

-- Q1 — Overall default rate (client grain)
SELECT ROUND(AVG(default_payment_next_month), 4) AS overall_default_rate,
       COUNT(*)                                   AS total_clients
FROM bigdata_etl.dim_client;

-- Q2 — Default rate by sex
SELECT sex_label,
       COUNT(*)                                   AS clients,
       ROUND(AVG(default_payment_next_month), 4)  AS default_rate
FROM bigdata_etl.dim_client
GROUP BY sex_label
ORDER BY default_rate DESC;

-- Q3 — Default rate by education
SELECT education_label,
       COUNT(*)                                   AS clients,
       ROUND(AVG(default_payment_next_month), 4)  AS default_rate
FROM bigdata_etl.dim_client
GROUP BY education_label
ORDER BY default_rate DESC;

-- Q4 — Default rate by marriage
SELECT marriage_label,
       COUNT(*)                                   AS clients,
       ROUND(AVG(default_payment_next_month), 4)  AS default_rate
FROM bigdata_etl.dim_client
GROUP BY marriage_label
ORDER BY default_rate DESC;

-- Q5 — Default rate by age band
SELECT age_band,
       COUNT(*)                                   AS clients,
       ROUND(AVG(default_payment_next_month), 4)  AS default_rate
FROM bigdata_etl.dim_client
GROUP BY age_band
ORDER BY age_band;

-- Q6 — Monthly behaviour trend (utilization, payment ratio, avg bill)
SELECT d.date_key,
       d.month_name,
       ROUND(AVG(f.credit_utilization), 4) AS avg_credit_utilization,
       ROUND(AVG(f.payment_ratio), 4)      AS avg_payment_ratio,
       ROUND(AVG(f.bill_amt), 2)           AS avg_bill_amt
FROM bigdata_etl.fact_credit_monthly f
JOIN bigdata_etl.dim_date d ON f.date_key = d.date_key
GROUP BY d.date_key, d.month_name
ORDER BY d.date_key;

-- Q7 — Monthly default rate aligned with macro indicators (Apr–Sep 2005)
SELECT d.date_key,
       d.month_name,
       ROUND(AVG(f.exchange_rate_twd_usd), 4) AS avg_fx_twd_usd,
       ROUND(AVG(f.real_broad_eer), 4)        AS avg_real_broad_eer,
       ROUND(AVG(f.total_reserves), 2)        AS avg_total_reserves,
       ROUND(AVG(f.default_payment_next_month), 4) AS default_rate
FROM bigdata_etl.fact_credit_monthly f
JOIN bigdata_etl.dim_date d ON f.date_key = d.date_key
GROUP BY d.date_key, d.month_name
ORDER BY d.date_key;

-- Q8 — Correlation of default vs macro indicators (single-row KPI)
SELECT ROUND(CORR(default_payment_next_month, exchange_rate_twd_usd), 4) AS corr_default_fx,
       ROUND(CORR(default_payment_next_month, real_broad_eer), 4)        AS corr_default_reer,
       ROUND(CORR(default_payment_next_month, total_reserves), 4)        AS corr_default_reserves
FROM bigdata_etl.fact_credit_monthly;
