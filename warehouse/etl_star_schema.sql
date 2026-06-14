-- ============================================================================
-- ETL warehouse — star schema DDL (CLAUDE.md §6.3)   [reference / documentation]
-- Database: bigdata_etl   |   Grain: fact = one row per client × billing month.
-- load.py creates the tables programmatically from the Transform parquet output;
-- this file documents the schema + the PK/FK constraints it applies.
-- Hive constraints are informational: DISABLE NOVALIDATE RELY.
-- ============================================================================
CREATE DATABASE IF NOT EXISTS bigdata_etl;

-- ----------------------------------------------------------------- dim_client
CREATE TABLE IF NOT EXISTS bigdata_etl.dim_client (
  id                          BIGINT,
  sex                         INT,
  sex_label                   STRING,
  education                   INT,
  education_label             STRING,
  marriage                    INT,
  marriage_label              STRING,
  age                         INT,
  age_band                    STRING,
  default_payment_next_month  INT,
  avg_delay_months            DOUBLE,   -- engineered
  num_months_delayed          INT,      -- engineered
  total_bill_amt              DOUBLE,
  total_pay_amt               DOUBLE,
  repayment_gap               DOUBLE    -- engineered
) STORED AS PARQUET;

-- ------------------------------------------------------------------- dim_date
CREATE TABLE IF NOT EXISTS bigdata_etl.dim_date (
  date_key          INT,        -- yyyymm, e.g. 200509
  full_date         DATE,
  year              INT,
  month             INT,
  month_name        STRING,
  quarter           INT,
  is_billing_month  BOOLEAN     -- TRUE for Apr–Sep 2005
) STORED AS PARQUET;

-- ------------------------------------------------------------------ dim_macro
CREATE TABLE IF NOT EXISTS bigdata_etl.dim_macro (
  date_key                 INT,    -- FK -> dim_date
  exchange_rate_twd_usd    DOUBLE, -- EXTAUS
  real_broad_eer           DOUBLE, -- RBTWBIS
  nominal_broad_eer        DOUBLE, -- NBTWBIS
  total_reserves           DOUBLE, -- TRESEGTWM194N
  exchange_rate_twd_usd_norm DOUBLE,
  real_broad_eer_norm        DOUBLE,
  total_reserves_norm        DOUBLE
) STORED AS PARQUET;

-- ------------------------------------------------------- fact_credit_monthly
CREATE TABLE IF NOT EXISTS bigdata_etl.fact_credit_monthly (
  id                          BIGINT,   -- FK -> dim_client
  date_key                    INT,      -- FK -> dim_date
  month                       INT,
  month_name                  STRING,
  limit_bal                   DOUBLE,
  pay_status                  INT,
  bill_amt                    DOUBLE,
  pay_amt                     DOUBLE,
  credit_utilization          DOUBLE,   -- engineered (monthly)
  payment_ratio               DOUBLE,   -- engineered (monthly)
  exchange_rate_twd_usd       DOUBLE,   -- macro enrichment (joined via date_key)
  real_broad_eer              DOUBLE,
  nominal_broad_eer           DOUBLE,
  total_reserves              DOUBLE,
  default_payment_next_month  INT
) STORED AS PARQUET;

-- ------------------------------------------------------------- PK/FK (informational)
ALTER TABLE bigdata_etl.dim_client          ADD CONSTRAINT pk_client     PRIMARY KEY (id)       DISABLE NOVALIDATE RELY;
ALTER TABLE bigdata_etl.dim_date            ADD CONSTRAINT pk_date       PRIMARY KEY (date_key) DISABLE NOVALIDATE RELY;
ALTER TABLE bigdata_etl.dim_macro           ADD CONSTRAINT pk_macro      PRIMARY KEY (date_key) DISABLE NOVALIDATE RELY;
ALTER TABLE bigdata_etl.fact_credit_monthly ADD CONSTRAINT fk_fact_client FOREIGN KEY (id)       REFERENCES bigdata_etl.dim_client(id)     DISABLE NOVALIDATE RELY;
ALTER TABLE bigdata_etl.fact_credit_monthly ADD CONSTRAINT fk_fact_date   FOREIGN KEY (date_key) REFERENCES bigdata_etl.dim_date(date_key)  DISABLE NOVALIDATE RELY;
