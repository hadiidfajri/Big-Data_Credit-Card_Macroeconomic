"""ETL — Stage 1: Extract (CLAUDE.md §6.1).

Pulls the two raw sources and lands them in ``raw/`` **untouched** (no cleaning,
no renaming, no type coercion — that happens in Transform):

* :func:`extract_etl_source1` — UCI *Default of Credit Card Clients* (id 350),
  saved as the original ``.xls`` (CSV fallback via ``ucimlrepo``).
* :func:`extract_etl_source2` — 4 FRED Taiwan series (``EXTAUS``, ``RBTWBIS``,
  ``NBTWBIS``, ``TRESEGTWM194N``) for 2005, saved as raw JSON.

Each source emits a structured log record (stage, source, rows, cols, size,
duration, status) to ``etl_pipeline/logs/`` per the project conventions (§11).

Run locally::

    python etl_pipeline/extract.py

or inside the Spark cluster image (deps already baked in)::

    docker compose exec spark-master python /app/etl_pipeline/extract.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# --------------------------------------------------------------------------- #
# Paths & constants
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "raw"
LOG_DIR = REPO_ROOT / "etl_pipeline" / "logs"
METADATA_FILE = LOG_DIR / "extract_metadata.jsonl"

UCI_ZIP_URL = (
    "https://archive.ics.uci.edu/static/public/350/"
    "default+of+credit+card+clients.zip"
)
UCI_DATASET_ID = 350

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
# dim_macro — FINAL (CLAUDE.md §3): FX + reserves, monthly, cover 2005.
FRED_SERIES = ["EXTAUS", "RBTWBIS", "NBTWBIS", "TRESEGTWM194N"]
DEFAULT_YEAR = 2005

HTTP_TIMEOUT = 60  # seconds


# --------------------------------------------------------------------------- #
# Logging / structured metadata
# --------------------------------------------------------------------------- #
logger = logging.getLogger("etl.extract")


def _configure_logging() -> None:
    """Console + file logging into ``etl_pipeline/logs/extract.log``."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    if logger.handlers:  # idempotent if called twice / imported
        return
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")

    console = logging.StreamHandler(stream=sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(LOG_DIR / "extract.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


@dataclass
class ExtractRecord:
    """One structured log record per extracted source (§11)."""

    stage: str
    source: str
    file: str
    rows: int | None
    cols: int | None
    size_bytes: int | None
    duration_s: float
    status: str
    ts: str


def _record(rec: ExtractRecord) -> ExtractRecord:
    """Emit a record to the human log and append it to the JSONL metadata file."""
    size_kb = f"{rec.size_bytes / 1024:.1f} KB" if rec.size_bytes else "-"
    logger.info(
        "[%s] source=%s status=%s rows=%s cols=%s size=%s duration=%.2fs file=%s",
        rec.stage,
        rec.source,
        rec.status,
        rec.rows,
        rec.cols,
        size_kb,
        rec.duration_s,
        rec.file,
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with METADATA_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(rec)) + "\n")
    return rec


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Source 1 — UCI Default of Credit Card Clients (id 350)
# --------------------------------------------------------------------------- #
def extract_etl_source1(raw_dir: Path = RAW_DIR) -> Path:
    """Extract the UCI credit-card dataset and save it raw to ``raw/``.

    Primary path downloads the official UCI ``.zip`` and saves the original
    ``.xls`` untouched. If that fails (URL change / network), it falls back to
    the ``ucimlrepo`` API and saves the original table as ``.csv``.

    Returns the path to the saved raw file.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    try:
        out_path = _download_uci_excel(raw_dir)
        # Count rows/cols only (no cleaning persisted). The UCI sheet has a
        # 2-row header: row 0 = X1..X23/Y group labels, row 1 = real names.
        df = pd.read_excel(out_path, header=1)
    except Exception as exc:  # noqa: BLE001 — fall back on any download/parse error
        logger.warning("UCI direct download failed (%s) — falling back to ucimlrepo.", exc)
        out_path, df = _download_uci_via_ucimlrepo(raw_dir)

    duration = time.perf_counter() - start
    _record(
        ExtractRecord(
            stage="extract",
            source="uci_credit_card_default (id 350)",
            file=str(out_path.relative_to(REPO_ROOT)),
            rows=int(df.shape[0]),
            cols=int(df.shape[1]),
            size_bytes=out_path.stat().st_size,
            duration_s=round(duration, 3),
            status="OK",
            ts=_now_iso(),
        )
    )
    return out_path


def _download_uci_excel(raw_dir: Path) -> Path:
    """Download the UCI zip and extract the original Excel file (raw)."""
    resp = requests.get(UCI_ZIP_URL, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # The archive holds a single .xls; pick the first Excel member.
        excel_name = next(
            name for name in zf.namelist() if name.lower().endswith((".xls", ".xlsx"))
        )
        suffix = Path(excel_name).suffix.lower()
        out_path = raw_dir / f"uci_credit_card{suffix}"
        with zf.open(excel_name) as src, out_path.open("wb") as dst:
            dst.write(src.read())  # raw bytes, untouched
    return out_path


def _download_uci_via_ucimlrepo(raw_dir: Path) -> tuple[Path, pd.DataFrame]:
    """Fallback: fetch via ucimlrepo and save the original table as CSV."""
    from ucimlrepo import fetch_ucirepo

    dataset = fetch_ucirepo(id=UCI_DATASET_ID)
    df = dataset.data.original  # full table as provided by UCI
    out_path = raw_dir / "uci_credit_card.csv"
    df.to_csv(out_path, index=False)  # raw content, no cleaning
    return out_path, df


# --------------------------------------------------------------------------- #
# Source 2 — FRED Taiwan macro series (JSON)
# --------------------------------------------------------------------------- #
def extract_etl_source2(
    raw_dir: Path = RAW_DIR,
    api_key: str | None = None,
    year: int = DEFAULT_YEAR,
    series_ids: list[str] | None = None,
) -> list[Path]:
    """Extract the FRED Taiwan series for ``year`` and save raw JSON per series.

    One ``raw/fred_<series_id>_<year>.json`` file per series, holding the
    untouched API response. Returns the list of saved paths. A failing series
    is logged with status ``FAILED`` and skipped (others still proceed).
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    api_key = api_key or os.getenv("FRED_API_KEY")
    if not api_key or api_key == "your_fred_api_key_here":
        raise RuntimeError(
            "FRED_API_KEY is missing or still the placeholder. "
            "Copy .env.example to .env and set a real key "
            "(https://fred.stlouisfed.org/docs/api/api_key.html)."
        )

    series_ids = series_ids or FRED_SERIES
    saved: list[Path] = []

    for series_id in series_ids:
        start = time.perf_counter()
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": f"{year}-01-01",
            "observation_end": f"{year}-12-31",
        }
        try:
            resp = requests.get(FRED_BASE_URL, params=params, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            observations = payload.get("observations", [])

            out_path = raw_dir / f"fred_{series_id}_{year}.json"
            # Persist the raw response untouched (pretty-printed for readability).
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            saved.append(out_path)

            n_cols = len(observations[0]) if observations else 0
            _record(
                ExtractRecord(
                    stage="extract",
                    source=f"fred:{series_id}",
                    file=str(out_path.relative_to(REPO_ROOT)),
                    rows=len(observations),
                    cols=n_cols,
                    size_bytes=out_path.stat().st_size,
                    duration_s=round(time.perf_counter() - start, 3),
                    status="OK",
                    ts=_now_iso(),
                )
            )
        except Exception as exc:  # noqa: BLE001 — keep extracting remaining series
            logger.error("FRED series %s failed: %s", series_id, exc)
            _record(
                ExtractRecord(
                    stage="extract",
                    source=f"fred:{series_id}",
                    file="-",
                    rows=None,
                    cols=None,
                    size_bytes=None,
                    duration_s=round(time.perf_counter() - start, 3),
                    status="FAILED",
                    ts=_now_iso(),
                )
            )

    return saved


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    """Run both extractions and return a process exit code."""
    _configure_logging()
    load_dotenv(REPO_ROOT / ".env")

    logger.info("=== ETL Extract started — raw dir: %s ===", RAW_DIR)
    failures = 0

    try:
        extract_etl_source1()
    except Exception as exc:  # noqa: BLE001
        logger.error("Source 1 (UCI) extraction failed: %s", exc)
        failures += 1

    try:
        saved = extract_etl_source2()
        if len(saved) < len(FRED_SERIES):
            failures += 1  # at least one series failed (already logged)
    except Exception as exc:  # noqa: BLE001
        logger.error("Source 2 (FRED) extraction failed: %s", exc)
        failures += 1

    status = "with errors" if failures else "successfully"
    logger.info("=== ETL Extract finished %s (failures=%d) ===", status, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
