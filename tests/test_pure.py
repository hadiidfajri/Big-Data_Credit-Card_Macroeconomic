"""Pure-Python unit tests (no Spark) — fast.

Covers: common.paths, common.metrics, transform.to_snake, docs/build_pdfs.md_to_html,
report/build_report_pdf.link_callback, dashboard/export_kpis_csv constants.
"""

from __future__ import annotations

import json

import pytest


# --------------------------------------------------------------------------- #
# common.paths
# --------------------------------------------------------------------------- #
def test_paths_relationships():
    from common import paths

    assert paths.STAGING_DIR == paths.WAREHOUSE_DIR / "staging"
    assert paths.METRICS_FILE == paths.METRICS_DIR / "pipeline_metrics.jsonl"
    assert paths.REPO_ROOT.exists()
    # importing must NOT create directories (read-only by design)
    assert paths.HIVE_WAREHOUSE == "/opt/hive/data/warehouse"


def test_ensure_dirs_creates(tmp_path):
    from common.paths import ensure_dirs

    target = tmp_path / "a" / "b"
    assert not target.exists()
    ensure_dirs(target)
    assert target.is_dir()


# --------------------------------------------------------------------------- #
# common.metrics
# --------------------------------------------------------------------------- #
def test_stage_timer_ok_writes_metric(tmp_path, monkeypatch):
    from common import metrics

    out = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(metrics, "METRICS_FILE", out)

    with metrics.stage_timer("ETL", "transform") as m:
        m.rows = 123

    assert out.exists()
    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["pipeline"] == "ETL"
    assert rec["stage"] == "transform"
    assert rec["status"] == "OK"
    assert rec["rows"] == 123
    assert rec["duration_s"] >= 0


def test_stage_timer_failed_reraises(tmp_path, monkeypatch):
    from common import metrics

    out = tmp_path / "metrics.jsonl"
    monkeypatch.setattr(metrics, "METRICS_FILE", out)

    with pytest.raises(ValueError):
        with metrics.stage_timer("ELT", "load"):
            raise ValueError("boom")

    rec = json.loads(out.read_text(encoding="utf-8").strip())
    assert rec["status"] == "FAILED"
    assert "boom" in rec["extra"]["error"]


def test_stage_metric_defaults():
    from common.metrics import StageMetric

    m = StageMetric(pipeline="ETL", stage="x")
    assert m.status == "OK"
    assert m.rows is None
    assert m.extra == {}


# --------------------------------------------------------------------------- #
# transform.to_snake  (pure string helper)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [
    ("Default Payment Next Month", "default_payment_next_month"),
    ("  LIMIT_BAL  ", "limit_bal"),
    ("default.payment.next.month", "default_payment_next_month"),
    ("PAY-0", "pay_0"),
    ("already_snake", "already_snake"),
    ("Multiple   Spaces", "multiple_spaces"),
])
def test_to_snake(raw, expected):
    from etl_pipeline.transform import to_snake

    assert to_snake(raw) == expected


# --------------------------------------------------------------------------- #
# docs/build_pdfs.md_to_html  + find_edge
# --------------------------------------------------------------------------- #
def test_md_to_html_renders_table_and_code():
    import build_pdfs

    md = "# Judul\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```\ncode\n```\n"
    html = build_pdfs.md_to_html(md, "T")
    assert "<table>" in html
    assert "<pre>" in html and "code" in html
    assert "Judul" in html
    assert "<style>" in html  # stylesheet inlined


def test_find_edge_returns_str_or_none():
    import build_pdfs

    edge = build_pdfs.find_edge()
    assert edge is None or isinstance(edge, str)


# --------------------------------------------------------------------------- #
# report/build_report_pdf.link_callback
# --------------------------------------------------------------------------- #
def test_link_callback_resolves_repo_file():
    import build_report_pdf
    from pathlib import Path

    # architecture_diagram.png exists at repo root -> resolved to an absolute path
    resolved = build_report_pdf.link_callback("architecture_diagram.png", "")
    assert Path(resolved).is_absolute()
    assert Path(resolved).exists()


def test_link_callback_passthrough_unknown():
    import build_report_pdf

    uri = "https://example.com/x.png"
    assert build_report_pdf.link_callback(uri, "") == uri


# --------------------------------------------------------------------------- #
# dashboard/export_kpis_csv constants + beeline hint
# --------------------------------------------------------------------------- #
def test_export_kpis_constants():
    import export_kpis_csv

    assert export_kpis_csv.KPI_TABLES == [
        "kpi_overall", "kpi_default_by_demographic",
        "kpi_monthly_default_vs_macro", "kpi_corr_default_macro",
    ]
    assert export_kpis_csv.DATABASES == ["bigdata_etl", "bigdata_elt"]


def test_beeline_hint_prints(capsys):
    import export_kpis_csv

    export_kpis_csv._beeline_hint()
    out = capsys.readouterr().out
    assert "beeline" in out
    assert "bigdata_etl__kpi_overall.csv" in out
