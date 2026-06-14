"""PySpark unit tests for etl_pipeline.transform (in-memory, no Hive/Parquet).

Marked ``spark`` — they use the session-scoped local SparkSession from conftest.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.spark

CREDIT_SCHEMA_COLS = (
    ["id", "limit_bal", "sex", "education", "marriage", "age",
     "default_payment_next_month"]
    + ["pay_0", "pay_2", "pay_3", "pay_4", "pay_5", "pay_6"]
    + [f"bill_amt{i}" for i in range(1, 7)]
    + [f"pay_amt{i}" for i in range(1, 7)]
)


def _make_credit(spark):
    """Two synthetic clients with all columns the transform functions expect."""
    # client 1: female/university/married/age45, default=1, mixed delays
    c1 = ([1, 10000.0, 2, 2, 1, 45, 1]
          + [2, 0, -1, 0, 1, 0]              # pay_0,pay_2..6
          + [1000.0] * 6                      # bill_amt1..6
          + [400.0] * 6)                      # pay_amt1..6
    # client 2: male/grad/single/age25, default=0, no delays
    c2 = ([2, 20000.0, 1, 1, 2, 25, 0]
          + [0, 0, 0, 0, 0, 0]
          + [2000.0] * 6
          + [2000.0] * 6)
    return spark.createDataFrame([c1, c2], CREDIT_SCHEMA_COLS)


def _make_macro(spark):
    """Minimal macro frame with the 6 billing-month date_keys."""
    rows = [(200500 + m, 30.0 + m) for m in (4, 5, 6, 7, 8, 9)]
    return spark.createDataFrame(rows, ["date_key", "exchange_rate_twd_usd"])


# --------------------------------------------------------------------------- #
def test_standardise_columns(spark):
    from etl_pipeline.transform import standardise_columns

    df = spark.createDataFrame([(1, 0)], ["LIMIT_BAL", "default.payment.next.month"])
    out = standardise_columns(df)
    assert "limit_bal" in out.columns
    assert "default_payment_next_month" in out.columns

    df2 = spark.createDataFrame([(1,)], ["y"])
    assert "default_payment_next_month" in standardise_columns(df2).columns


def test_iqr_cap_winsorises_outlier(spark):
    from etl_pipeline.transform import iqr_cap

    df = spark.createDataFrame([(float(x),) for x in [1, 2, 3, 4, 5, 100]], ["v"])
    capped = iqr_cap(df, "v")
    mx = capped.agg({"v": "max"}).first()[0]
    assert mx < 100            # the 100 outlier was pulled in to the IQR fence
    assert mx <= 8


def test_load_macro_from_json(spark, tmp_path, monkeypatch):
    from etl_pipeline import transform

    obs = [{"date": f"2005-{m:02d}-01", "value": str(31.0 + m)} for m in range(1, 13)]
    (tmp_path / "fred_EXTAUS_2005.json").write_text(
        json.dumps({"observations": obs}), encoding="utf-8")
    monkeypatch.setattr(transform, "RAW_DIR", tmp_path)

    macro = transform.load_macro(spark)
    assert macro.count() == 12
    assert "date_key" in macro.columns
    assert "exchange_rate_twd_usd" in macro.columns
    # nominal_broad_eer file absent -> column present but all null
    assert "nominal_broad_eer" in macro.columns
    jan = macro.filter("date_key = 200501").first()
    assert jan["exchange_rate_twd_usd"] == pytest.approx(32.0)
    assert jan["nominal_broad_eer"] is None


def test_normalise_macro_range(spark):
    from etl_pipeline.transform import normalise_macro

    rows = [(31.0, 100.0, 150.0), (32.0, 105.0, 160.0), (33.0, 110.0, 170.0)]
    df = spark.createDataFrame(rows, ["exchange_rate_twd_usd", "real_broad_eer", "total_reserves"])
    out = normalise_macro(df)
    for col in ("exchange_rate_twd_usd_norm", "real_broad_eer_norm", "total_reserves_norm"):
        assert col in out.columns
        lo, hi = out.agg({col: "min"}).first()[0], out.agg({col: "max"}).first()[0]
        assert lo == pytest.approx(0.0)
        assert hi == pytest.approx(1.0)


def test_build_dim_date(spark):
    from etl_pipeline.transform import build_dim_date

    dd = build_dim_date(spark)
    assert dd.count() == 12
    billing = {r["month"] for r in dd.filter("is_billing_month").collect()}
    assert billing == {4, 5, 6, 7, 8, 9}
    apr = dd.filter("month = 4").first()
    assert apr["quarter"] == 2
    assert apr["date_key"] == 200504


def test_build_dim_client_features(spark):
    from etl_pipeline.transform import build_dim_client

    dim = build_dim_client(_make_credit(spark))
    r1 = dim.filter("id = 1").first()
    assert r1["sex_label"] == "female"
    assert r1["education_label"] == "university"
    assert r1["marriage_label"] == "married"
    assert r1["age_band"] == "40-49"
    assert r1["avg_delay_months"] == pytest.approx(round((2 + 0 - 1 + 0 + 1 + 0) / 6, 3))
    assert r1["num_months_delayed"] == 2
    assert r1["total_bill_amt"] == pytest.approx(6000.0)
    assert r1["total_pay_amt"] == pytest.approx(2400.0)
    assert r1["repayment_gap"] == pytest.approx(3600.0)


def test_build_fact_unpivot_and_features(spark):
    from etl_pipeline.transform import build_fact

    credit = _make_credit(spark)
    fact = build_fact(credit, _make_macro(spark))
    # 2 clients x 6 months = 12 rows
    assert fact.count() == 12
    c1 = fact.filter("id = 1").collect()
    assert len(c1) == 6
    sep = [r for r in c1 if r["date_key"] == 200509][0]
    assert sep["credit_utilization"] == pytest.approx(1000.0 / 10000.0)
    assert sep["payment_ratio"] == pytest.approx(400.0 / 1000.0)
    # macro joined in
    assert "exchange_rate_twd_usd" in fact.columns


def test_build_fact_zero_limit_fills_zero(spark):
    from etl_pipeline.transform import build_fact

    row = ([3, 0.0, 1, 1, 1, 30, 0] + [0] * 6 + [500.0] * 6 + [100.0] * 6)
    credit = spark.createDataFrame([row], CREDIT_SCHEMA_COLS)
    fact = build_fact(credit, _make_macro(spark))
    # limit_bal = 0 -> utilization division null -> filled with 0.0
    utils = {r["credit_utilization"] for r in fact.collect()}
    assert utils == {0.0}


def test_validate_all_pass_and_dupe_fails(spark):
    from etl_pipeline.transform import (build_dim_client, build_dim_date,
                                        build_fact, validate)

    credit = _make_credit(spark)
    dim_date = build_dim_date(spark)
    dim_client = build_dim_client(credit)
    fact = build_fact(credit, _make_macro(spark))

    res = validate(fact, dim_client, dim_date)
    assert all(rule["pass"] for rule in res.values()), res
    assert res["distribution_default_rate"]["default_rate"] == pytest.approx(0.5)

    # inject a duplicate (id, date_key) -> uniqueness rule must fail
    dupe = fact.unionByName(fact.limit(1))
    res2 = validate(dupe, dim_client, dim_date)
    assert res2["uniqueness_id_date"]["pass"] is False
