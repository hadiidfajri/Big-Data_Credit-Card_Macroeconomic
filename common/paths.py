"""Canonical project directories, resolved from the repo root.

Importing this module never creates directories; call :func:`ensure_dirs` (or the
per-path ``mkdir``) when a writer actually needs them, so read-only tools stay
side-effect free.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Source landing zones
RAW_DIR = REPO_ROOT / "raw"               # ETL raw landing (untouched)
DATALAKE_DIR = REPO_ROOT / "datalake"     # ELT raw landing (untouched)

# Pipeline dirs
ETL_DIR = REPO_ROOT / "etl_pipeline"
ELT_DIR = REPO_ROOT / "elt_pipeline"
SYNTHETIC_DIR = REPO_ROOT / "synthetic"
WAREHOUSE_DIR = REPO_ROOT / "warehouse"
DASHBOARD_DIR = REPO_ROOT / "dashboard"
ANALYSIS_DIR = REPO_ROOT / "analysis"
REPORT_DIR = REPO_ROOT / "report"

# Transform output (parquet) consumed by Load
STAGING_DIR = WAREHOUSE_DIR / "staging"

# Logs
ETL_LOGS = ETL_DIR / "logs"
ELT_LOGS = ELT_DIR / "logs"
METRICS_DIR = REPO_ROOT / "logs"          # cross-cutting metrics for Prompt 9
METRICS_FILE = METRICS_DIR / "pipeline_metrics.jsonl"

# Hive warehouse path INSIDE the containers (shared volume, same path everywhere)
HIVE_WAREHOUSE = "/opt/hive/data/warehouse"


def ensure_dirs(*paths: Path) -> None:
    """Create each given directory (and parents) if missing."""
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
