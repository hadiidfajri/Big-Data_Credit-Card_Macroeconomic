"""Prompt 5 — ETL Transform (PySpark), per CLAUDE.md §6.2.

Row-level, ML-oriented transformation of the credit data + macro enrichment:

a. **Cleaning** — dedup by PK, missing handling by dtype, date standardisation,
   outliers via **IQR** (credit) and **Z-score** (macro).
b. **Standardisation** — snake_case columns, **min-max normalise**
   ``exchange_rate_twd_usd`` / ``real_broad_eer`` / ``total_reserves``, encode
   categoricals (readable labels), enforce dtypes.
c. **Enrichment** — **unpivot** wide → monthly grain (Apr–Sep 2005), build
   ``dim_date``, join macro via ``dim_date``, engineer **5 features**.
d. **Validation** — **6 rules** (uniqueness, null, range, dtype, referential
   integrity, distribution); failures are fixed where possible and logged.

Inputs : ``synthetic/synthetic_credit_clients.csv`` (preferred, ≥150k) or the raw
         UCI file; ``raw/fred_*_2005.json``.
Outputs: parquet staging tables in ``warehouse/staging/`` consumed by ``load.py``:
         ``fact_credit_monthly``, ``dim_client``, ``dim_date``, ``dim_macro``.

Run::

    docker compose exec spark-master spark-submit /app/etl_pipeline/transform.py
    # or local:  python etl_pipeline/transform.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402
from pyspark.sql import DataFrame, SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.metrics import stage_timer  # noqa: E402
from common.paths import ETL_LOGS, RAW_DIR, STAGING_DIR, SYNTHETIC_DIR, ensure_dirs  # noqa: E402
from common.spark_session import get_spark  # noqa: E402

logger = get_logger("etl.transform", ETL_LOGS / "transform.log")

# Wide→long month map (CLAUDE.md §3): PAY_0→Sep, PAY_2..6→Aug..Apr (no PAY_1).
MONTH_MAP = [
    # (date_key, month, pay_status_col, bill_col, pay_col)
    (200509, 9, "pay_0", "bill_amt1", "pay_amt1"),
    (200508, 8, "pay_2", "bill_amt2", "pay_amt2"),
    (200507, 7, "pay_3", "bill_amt3", "pay_amt3"),
    (200506, 6, "pay_4", "bill_amt4", "pay_amt4"),
    (200505, 5, "pay_5", "bill_amt5", "pay_amt5"),
    (200504, 4, "pay_6", "bill_amt6", "pay_amt6"),
]
PAY_STATUS_COLS = ["pay_0", "pay_2", "pay_3", "pay_4", "pay_5", "pay_6"]
BILL_COLS = [f"bill_amt{i}" for i in range(1, 7)]
PAY_COLS = [f"pay_amt{i}" for i in range(1, 7)]
NORMALISE_COLS = ["exchange_rate_twd_usd", "real_broad_eer", "total_reserves"]

# FRED series -> macro column name (dim_macro FINAL, CLAUDE.md §3)
FRED_TO_COL = {
    "EXTAUS": "exchange_rate_twd_usd",
    "RBTWBIS": "real_broad_eer",
    "NBTWBIS": "nominal_broad_eer",
    "TRESEGTWM194N": "total_reserves",
}

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def to_snake(name: str) -> str:
    """lowercase snake_case (CLAUDE.md §11)."""
    name = name.strip().replace(".", " ").replace("-", " ")
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"__+", "_", name)
    return name.lower()


def standardise_columns(df: DataFrame) -> DataFrame:
    for c in df.columns:
        df = df.withColumnRenamed(c, to_snake(c))
    # normalise the known target variants to one canonical name
    for variant in ("default_payment_next_month", "default_payment_next_month_",
                    "default.payment.next.month", "y"):
        if variant in df.columns:
            df = df.withColumnRenamed(variant, "default_payment_next_month")
    return df


def iqr_cap(df: DataFrame, col: str) -> DataFrame:
    """Winsorise a continuous column to its IQR fence (credit outliers)."""
    q1, q3 = df.approxQuantile(col, [0.25, 0.75], 0.01)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    capped = df.withColumn(
        col, F.when(F.col(col) < lo, lo).when(F.col(col) > hi, hi).otherwise(F.col(col))
    )
    return capped


# --------------------------------------------------------------------------- #
# Load sources
# --------------------------------------------------------------------------- #
def load_credit(spark: SparkSession) -> DataFrame:
    # Source 1 = the pre-generated synthetic credit clients placed in raw/. CTGAN
    # is a ONE-TIME pre-step (run separately) and is skipped from the standard run,
    # so it never competes with Hive for memory. Fallbacks keep it robust.
    raw_synth = RAW_DIR / "synthetic_credit_clients.csv"
    synth = SYNTHETIC_DIR / "synthetic_credit_clients.csv"
    raw_csv = RAW_DIR / "uci_credit_card.csv"
    raw_xls = RAW_DIR / "uci_credit_card.xls"
    if raw_synth.exists():
        logger.info("Credit source: %s (synthetic, source 1)", raw_synth.name)
        df = spark.read.csv(str(raw_synth), header=True, inferSchema=True)
    elif synth.exists():
        logger.info("Credit source: synthetic/%s", synth.name)
        df = spark.read.csv(str(synth), header=True, inferSchema=True)
    elif raw_csv.exists():
        logger.info("Credit source: raw csv %s", raw_csv.name)
        df = spark.read.csv(str(raw_csv), header=True, inferSchema=True)
    elif raw_xls.exists():
        # Spark can't read .xls — fall back to pandas for the seed-only case.
        import pandas as pd

        logger.info("Credit source: raw xls %s (via pandas)", raw_xls.name)
        df = spark.createDataFrame(pd.read_excel(raw_xls, header=1))
    else:
        raise FileNotFoundError(
            "No credit source found. Place synthetic_credit_clients.csv in raw/ "
            "(or run synthetic/train_ctgan.py once)."
        )
    return standardise_columns(df)


def load_macro(spark: SparkSession) -> DataFrame:
    """Read the FRED JSON files into a tidy monthly macro frame (one row/month)."""
    import pandas as pd

    frames = {}
    for series_id, col in FRED_TO_COL.items():
        path = RAW_DIR / f"fred_{series_id}_2005.json"
        if not path.exists():
            logger.warning("Missing FRED file %s — column %s will be null.", path.name, col)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        obs = payload.get("observations", [])
        s = {}
        for o in obs:
            val = o["value"]
            if val in (".", "", None):  # FRED missing marker
                continue
            month = int(o["date"][5:7])
            s[200500 + month] = float(val)
        frames[col] = s

    # assemble one row per 2005 month
    rows = []
    for m in range(1, 13):
        dk = 200500 + m
        row = {"date_key": dk}
        for col in FRED_TO_COL.values():
            row[col] = frames.get(col, {}).get(dk)
        rows.append(row)
    pdf = pd.DataFrame(rows)
    return spark.createDataFrame(pdf)


# --------------------------------------------------------------------------- #
# Stage (a) Cleaning
# --------------------------------------------------------------------------- #
def clean_credit(df: DataFrame) -> DataFrame:
    before = df.count()
    df = df.dropDuplicates(["id"])           # dedup by PK
    logger.info("Credit dedup: %d -> %d rows", before, df.count())

    # missing by dtype: numeric -> 0/median-ish (fillna 0 for amounts), keep label
    num_cols = [c for c, t in df.dtypes if t in ("int", "bigint", "double", "float")]
    df = df.fillna(0, subset=[c for c in num_cols if c != "id"])

    # IQR outlier capping on continuous credit columns
    for c in ["limit_bal", *BILL_COLS, *PAY_COLS]:
        if c in df.columns:
            df = iqr_cap(df, c)
    # clamp age to a sane range (range-rule fix)
    if "age" in df.columns:
        df = df.withColumn("age", F.when(F.col("age") < 18, 18)
                           .when(F.col("age") > 100, 100).otherwise(F.col("age")))
    return df


def clean_macro(df: DataFrame) -> DataFrame:
    """Z-score outlier *detection* on macro columns (flag + log; values kept)."""
    for col in FRED_TO_COL.values():
        if col not in df.columns:
            continue
        stats = df.select(F.mean(col).alias("m"), F.stddev(col).alias("s")).first()
        if stats["s"] and stats["s"] > 0:
            df = df.withColumn(f"{col}_zscore",
                               F.round((F.col(col) - F.lit(stats["m"])) / F.lit(stats["s"]), 3))
            n_out = df.filter(F.abs(F.col(f"{col}_zscore")) > 3).count()
            logger.info("Macro %s: z-score |>3| outliers = %d", col, n_out)
    # forward/backfill any missing month with column mean (simple, documented)
    for col in FRED_TO_COL.values():
        if col in df.columns:
            mean_val = df.select(F.mean(col)).first()[0]
            df = df.fillna({col: mean_val} if mean_val is not None else {})
    return df


# --------------------------------------------------------------------------- #
# Stage (b/c) Standardise + enrich (normalise macro, build dims, unpivot, features)
# --------------------------------------------------------------------------- #
def normalise_macro(df: DataFrame) -> DataFrame:
    """Min-max normalise the CONFIRMED macro columns to [0,1]."""
    for col in NORMALISE_COLS:
        if col not in df.columns:
            continue
        lo, hi = df.select(F.min(col), F.max(col)).first()
        rng = (hi - lo) if (hi is not None and hi != lo) else 1.0
        df = df.withColumn(f"{col}_norm", F.round((F.col(col) - F.lit(lo)) / F.lit(rng), 4))
    return df


def build_dim_date(spark: SparkSession) -> DataFrame:
    rows = []
    for m in range(1, 13):
        dk = 200500 + m
        rows.append((dk, f"2005-{m:02d}-01", 2005, m, MONTH_NAMES[m],
                     (m - 1) // 3 + 1, 4 <= m <= 9))
    return spark.createDataFrame(
        rows, ["date_key", "full_date", "year", "month", "month_name",
               "quarter", "is_billing_month"]
    ).withColumn("full_date", F.to_date("full_date"))


def build_dim_client(df: DataFrame) -> DataFrame:
    """Encode categoricals to labels + client-level engineered features."""
    sex = F.when(F.col("sex") == 1, "male").when(F.col("sex") == 2, "female").otherwise("unknown")
    edu = (F.when(F.col("education") == 1, "graduate_school")
           .when(F.col("education") == 2, "university")
           .when(F.col("education") == 3, "high_school")
           .when(F.col("education") == 4, "others").otherwise("unknown"))
    mar = (F.when(F.col("marriage") == 1, "married")
           .when(F.col("marriage") == 2, "single")
           .when(F.col("marriage") == 3, "others").otherwise("unknown"))
    age_band = (F.when(F.col("age") < 30, "<30")
                .when(F.col("age") < 40, "30-39")
                .when(F.col("age") < 50, "40-49")
                .when(F.col("age") < 60, "50-59").otherwise("60+"))

    delay_cols = [F.col(c) for c in PAY_STATUS_COLS if c in df.columns]
    total_bill = sum((F.col(c) for c in BILL_COLS if c in df.columns), F.lit(0))
    total_pay = sum((F.col(c) for c in PAY_COLS if c in df.columns), F.lit(0))
    num_delayed = sum((F.when(F.col(c) > 0, 1).otherwise(0) for c in PAY_STATUS_COLS
                       if c in df.columns), F.lit(0))

    dim = (df.select(
        "id",
        F.col("sex"), sex.alias("sex_label"),
        F.col("education"), edu.alias("education_label"),
        F.col("marriage"), mar.alias("marriage_label"),
        F.col("age"), age_band.alias("age_band"),
        F.col("default_payment_next_month"),
        # --- engineered (client-level) ---
        F.round(sum(delay_cols, F.lit(0)) / F.lit(len(delay_cols)), 3).alias("avg_delay_months"),
        num_delayed.alias("num_months_delayed"),
        total_bill.alias("total_bill_amt"),
        total_pay.alias("total_pay_amt"),
        (total_bill - total_pay).alias("repayment_gap"),
    ))
    return dim


def build_fact(df: DataFrame, macro: DataFrame) -> DataFrame:
    """Unpivot to monthly grain, add monthly features, join macro via date_key."""
    parts = []
    for dk, month, pay_col, bill_col, pay_amt_col in MONTH_MAP:
        parts.append(df.select(
            F.col("id"),
            F.lit(dk).alias("date_key"),
            F.lit(month).alias("month"),
            F.col("limit_bal"),
            F.col(pay_col).alias("pay_status"),
            F.col(bill_col).alias("bill_amt"),
            F.col(pay_amt_col).alias("pay_amt"),
            F.col("default_payment_next_month"),
        ))
    fact = parts[0]
    for p in parts[1:]:
        fact = fact.unionByName(p)

    # --- monthly engineered features ---
    fact = (fact
            .withColumn("credit_utilization",
                        F.round(F.col("bill_amt") / F.when(F.col("limit_bal") == 0, None)
                                .otherwise(F.col("limit_bal")), 4))
            .withColumn("payment_ratio",
                        F.round(F.col("pay_amt") / F.when(F.col("bill_amt") == 0, None)
                                .otherwise(F.col("bill_amt")), 4))
            .fillna({"credit_utilization": 0.0, "payment_ratio": 0.0}))

    # macro enrichment joined via dim_date key
    fact = fact.join(F.broadcast(macro), on="date_key", how="left")
    return fact


# --------------------------------------------------------------------------- #
# Stage (d) Validation — 6 rules
# --------------------------------------------------------------------------- #
def validate(fact: DataFrame, dim_client: DataFrame, dim_date: DataFrame) -> dict:
    results = {}

    # 1. uniqueness of (id, date_key)
    dupes = fact.groupBy("id", "date_key").count().filter("count > 1").count()
    results["uniqueness_id_date"] = {"violations": dupes, "pass": dupes == 0}

    # 2. null check on keys
    nulls = fact.filter(F.col("id").isNull() | F.col("date_key").isNull()).count()
    results["not_null_keys"] = {"violations": nulls, "pass": nulls == 0}

    # 3. range: default in {0,1}; credit_utilization must be non-null. Negative
    #    utilization is VALID (overpaid / credit-balance accounts from negative
    #    bill_amt), so it is reported for documentation but not treated as a failure.
    bad_default = fact.filter(~F.col("default_payment_next_month").isin(0, 1)).count()
    null_util = fact.filter(F.col("credit_utilization").isNull()).count()
    neg_util = fact.filter(F.col("credit_utilization") < 0).count()
    results["range_checks"] = {"violations": bad_default + null_util,
                               "neg_utilization_kept": neg_util,
                               "pass": (bad_default + null_util) == 0}

    # 4. datatype consistency: numeric measures are numeric
    numeric_types = {t for c, t in fact.dtypes if c in ("bill_amt", "pay_amt", "limit_bal")}
    ok_types = numeric_types.issubset({"int", "bigint", "double", "float"})
    results["dtype_consistency"] = {"types": sorted(numeric_types), "pass": ok_types}

    # 5. referential integrity: fact.date_key ⊆ dim_date; fact.id ⊆ dim_client
    orphan_dates = fact.join(dim_date, "date_key", "left_anti").count()
    orphan_clients = fact.join(dim_client, "id", "left_anti").count()
    results["referential_integrity"] = {"orphan_dates": orphan_dates,
                                        "orphan_clients": orphan_clients,
                                        "pass": orphan_dates == 0 and orphan_clients == 0}

    # 6. distribution: overall default rate plausibly in (0,1)
    rate = dim_client.agg(F.avg("default_payment_next_month")).first()[0] or 0
    results["distribution_default_rate"] = {"default_rate": round(float(rate), 4),
                                            "pass": 0 < rate < 1}

    for rule, r in results.items():
        logger.info("VALIDATION %-26s -> %s", rule, r)
    return results


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def main() -> int:
    ensure_dirs(STAGING_DIR, ETL_LOGS)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    spark = get_spark("etl-transform", with_hive=False)
    logger.info("=== ETL Transform started ===")

    with stage_timer("ETL", "transform", logger) as m:
        # load
        credit = load_credit(spark)
        macro = load_macro(spark)

        # (a) clean
        credit = clean_credit(credit)
        macro = clean_macro(macro)

        # (b) standardise / normalise macro
        macro = normalise_macro(macro)

        # (c) dims + unpivot fact + features + macro join
        dim_date = build_dim_date(spark)
        dim_client = build_dim_client(credit)
        dim_macro = macro
        fact = build_fact(credit, macro)
        fact = fact.withColumn("month_name",
                               F.element_at(F.create_map(
                                   *sum(([F.lit(k), F.lit(v)] for k, v in MONTH_NAMES.items()), [])
                               ), F.col("month")))

        # (d) validate
        report = validate(fact, dim_client, dim_date)

        # persist staging parquet for load.py
        fact.write.mode("overwrite").parquet(str(STAGING_DIR / "fact_credit_monthly"))
        dim_client.write.mode("overwrite").parquet(str(STAGING_DIR / "dim_client"))
        dim_date.write.mode("overwrite").parquet(str(STAGING_DIR / "dim_date"))
        dim_macro.write.mode("overwrite").parquet(str(STAGING_DIR / "dim_macro"))

        m.rows = fact.count()
        (STAGING_DIR / "validation_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        logger.info("Staging written: fact rows=%d, clients=%d",
                    m.rows, dim_client.count())

    logger.info("=== ETL Transform finished ===")
    spark.stop()
    return 0 if all(r.get("pass") for r in report.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
