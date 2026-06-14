"""Prompt 4 — CTGAN synthetic augmentation (SDV ``CTGANSynthesizer``).

Trains CTGAN on the UCI credit data and generates **>=150,000** synthetic clients
with a *controlled* target-class balance and a fixed seed for reproducibility
(CLAUDE.md §3). The augmented table becomes the primary credit dataset consumed
by both the ETL transform and the ELT warehouse load (before the FRED merge).

Output:
* ``synthetic/synthetic_credit_clients.csv`` — the generated clients.
* ``synthetic/ctgan_summary.json``           — run parameters + class balance.
  (Narrative method/bias notes for the report live in ``synthetic/CTGAN_METHOD.md``.)

Run (heavy — needs torch; prefer the Spark image or a GPU box)::

    python synthetic/train_ctgan.py --n 150000 --epochs 300 --seed 42
    python synthetic/train_ctgan.py --n 150000 --balance   # force ~50/50 default
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common.logging_utils import get_logger  # noqa: E402
from common.metrics import stage_timer  # noqa: E402
from common.paths import RAW_DIR, SYNTHETIC_DIR, ensure_dirs  # noqa: E402

logger = get_logger("synthetic.ctgan", SYNTHETIC_DIR / "ctgan.log")

TARGET_CANDIDATES = ("default payment next month", "default.payment.next.month", "Y")
CATEGORICAL_HINTS = ("SEX", "EDUCATION", "MARRIAGE")


def _set_seed(seed: int) -> None:
    """Seed every RNG CTGAN may touch for reproducibility (§11)."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except Exception:  # noqa: BLE001 — torch optional at import time
        pass


def load_seed_data() -> pd.DataFrame:
    """Load the original UCI credit table that CTGAN learns from."""
    xls = RAW_DIR / "uci_credit_card.xls"
    csv = RAW_DIR / "uci_credit_card.csv"
    if xls.exists():
        return pd.read_excel(xls, header=1)
    if csv.exists():
        return pd.read_csv(csv)
    raise FileNotFoundError(
        "No raw credit file in raw/. Run etl_pipeline/extract.py first."
    )


def find_target(df: pd.DataFrame) -> str:
    for cand in TARGET_CANDIDATES:
        if cand in df.columns:
            return cand
    # last resort: any column mentioning 'default'
    for col in df.columns:
        if "default" in col.lower():
            return col
    raise KeyError("Could not locate the default target column.")


def build_metadata(df: pd.DataFrame, target: str):
    """SDV metadata; mark demographics + target categorical for good modelling
    and to enable conditional (balanced) sampling."""
    from sdv.metadata import SingleTableMetadata

    md = SingleTableMetadata()
    md.detect_from_dataframe(df)
    for col in df.columns:
        if col == target or col.upper() in CATEGORICAL_HINTS:
            md.update_column(column_name=col, sdtype="categorical")
    if "ID" in df.columns:
        md.update_column(column_name="ID", sdtype="id")
        md.set_primary_key("ID")
    return md


def class_targets(real: pd.Series, n: int, balance: bool) -> dict:
    """Desired synthetic count per target class."""
    classes = sorted(real.dropna().unique().tolist())
    if balance:
        per = n // len(classes)
        return {c: per for c in classes}
    # preserve the original proportions
    props = real.value_counts(normalize=True)
    return {c: int(round(props.get(c, 0) * n)) for c in classes}


def generate(synth, target: str, counts: dict) -> pd.DataFrame:
    """Conditional sampling so the target-class balance is controlled, not random."""
    from sdv.sampling import Condition

    conditions = [
        Condition(num_rows=int(n), column_values={target: c})
        for c, n in counts.items()
        if n > 0
    ]
    return synth.sample_from_conditions(conditions=conditions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train CTGAN and generate synthetic clients.")
    parser.add_argument("--n", type=int, default=150_000, help="rows to generate (>=150000).")
    parser.add_argument("--epochs", type=int, default=300, help="CTGAN training epochs.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--balance", action="store_true",
                        help="Force ~50/50 default vs non-default (else preserve original ratio).")
    args = parser.parse_args()

    ensure_dirs(SYNTHETIC_DIR)
    _set_seed(args.seed)
    logger.info("=== CTGAN synthesis (n=%d, epochs=%d, seed=%d, balance=%s) ===",
                args.n, args.epochs, args.seed, args.balance)

    with stage_timer("SYNTHETIC", "ctgan", logger) as m:
        from sdv.single_table import CTGANSynthesizer

        real = load_seed_data()
        target = find_target(real)
        # Drop ID consistently for BOTH metadata and fit (surrogate IDs are
        # re-assigned after sampling); otherwise SDV rejects the data/metadata mismatch.
        real_features = real.drop(columns=[c for c in ("ID",) if c in real.columns])
        logger.info("Seed rows=%d, target column='%s'", len(real), target)

        metadata = build_metadata(real_features, target)
        synth = CTGANSynthesizer(metadata, epochs=args.epochs, verbose=True)
        synth.fit(real_features)

        counts = class_targets(real_features[target], args.n, args.balance)
        logger.info("Target class plan: %s", counts)
        synthetic = generate(synth, target, counts)

        # fresh surrogate IDs (original IDs are not meaningful post-synthesis)
        synthetic.insert(0, "ID", range(1, len(synthetic) + 1))
        out_csv = SYNTHETIC_DIR / "synthetic_credit_clients.csv"
        synthetic.to_csv(out_csv, index=False)
        m.rows = len(synthetic)

        balance = synthetic[target].value_counts(normalize=True).round(4).to_dict()
        summary = {
            "rows_generated": len(synthetic),
            "epochs": args.epochs,
            "seed": args.seed,
            "balance_mode": "50/50" if args.balance else "preserve_original",
            "target_column": target,
            "synthetic_class_balance": {str(k): v for k, v in balance.items()},
            "real_rows": len(real),
            "output_csv": str(out_csv.relative_to(Path(__file__).resolve().parents[1])),
        }
        (SYNTHETIC_DIR / "ctgan_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        logger.info("Wrote %d rows -> %s | class balance=%s", len(synthetic), out_csv, balance)

    logger.info("=== CTGAN done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
