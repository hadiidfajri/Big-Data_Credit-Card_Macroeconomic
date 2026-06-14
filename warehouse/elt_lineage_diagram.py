"""Render the ELT warehouse **table lineage** as an image.

bigdata_elt is not a star schema — it is a chain of materialised analytical tables
built by set-based SQL (CASE pivot, LATERAL VIEW stack, window functions, GROUPING
SETS). This draws raw -> derived -> KPI lineage with the SQL technique on each edge,
mirroring ``elt_pipeline/transform.sql`` + ``warehouse/dashboard_kpis.sql``.

Run::  python warehouse/elt_lineage_diagram.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent

RAW_C = "#e9d5ff"      # raw landing
INT_C = "#bae6fd"      # intermediate
ANA_C = "#bbf7d0"      # analytical
KPI_C = "#fde68a"      # kpi


def box(ax, x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                 linewidth=1.3, edgecolor="#334155", facecolor=color, zorder=2))
    ax.text(x + w / 2, y + h - 0.27, title, ha="center", va="center",
            fontsize=8.6, weight="bold", zorder=3)
    ax.text(x + w / 2, y + 0.30, sub, ha="center", va="center",
            fontsize=6.3, color="#475569", zorder=3)
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2),
            "t": (x + w / 2, y + h), "b": (x + w / 2, y),
            "cx": x + w / 2, "cy": y + h / 2}


def arrow(ax, p1, p2, label, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                 linewidth=1.4, color="#475569",
                 connectionstyle=f"arc3,rad={rad}", zorder=1))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ax.text(mx, my + 0.16 + rad * 2, label, ha="center", va="center", fontsize=6.2,
            color="#0f3d63", weight="bold",
            bbox=dict(boxstyle="round,pad=0.13", fc="white", ec="none", alpha=0.9), zorder=4)


def main() -> int:
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.set_title("ELT Warehouse — Table Lineage (bigdata_elt)  ·  set-based SQL",
                 fontsize=14, weight="bold")

    W, H = 3.4, 1.2
    # column x positions
    x1, x2, x3, x4 = 0.4, 4.5, 8.7, 13.1

    # col1 raw
    rcred = box(ax, x1, 6.8, W, H, "raw_credit", "150,000 x 25  (apa adanya)", RAW_C)
    rmac = box(ax, x1, 3.4, W, H, "raw_macro", "48 baris (long: series/obs/value)", RAW_C)

    # col2 intermediate
    efact = box(ax, x2, 6.8, W, H, "elt_fact_monthly", "900,000  (unpivot bulanan)", INT_C)
    emac = box(ax, x2, 3.4, W, H, "elt_macro_monthly", "12  (pivot makro/bulan)", INT_C)

    # col3 analytical
    etrend = box(ax, x3, 7.6, W, H, "elt_client_trends", "900,000  (tren per klien)", ANA_C)
    edemo = box(ax, x3, 5.0, W, H, "elt_default_by_demographic", "17  (per dimensi + total)", ANA_C)
    evsm = box(ax, x3, 2.4, W, H, "elt_default_vs_macro", "6  (default vs makro/bln)", ANA_C)

    # col4 kpi
    kw, kh = 3.5, 0.92
    k1 = box(ax, x4, 7.7, kw, kh, "kpi_overall", "default_rate, total_clients", KPI_C)
    k2 = box(ax, x4, 6.4, kw, kh, "kpi_default_by_demographic", "dimension, category, rate", KPI_C)
    k3 = box(ax, x4, 5.1, kw, kh, "kpi_monthly_default_vs_macro", "per bulan + makro", KPI_C)
    k4 = box(ax, x4, 3.8, kw, kh, "kpi_corr_default_macro", "corr_fx/reer/reserves", KPI_C)

    # edges (SQL technique on each)
    arrow(ax, rcred["r"], efact["l"], "LATERAL VIEW stack(6)")
    arrow(ax, rmac["r"], emac["l"], "CASE pivot + GROUP BY")
    arrow(ax, efact["r"], etrend["l"], "WINDOW LAG/RANK/AVG", rad=0.12)
    arrow(ax, rcred["b"], edemo["l"], "GROUPING SETS (OLAP)", rad=-0.25)
    arrow(ax, efact["r"], evsm["l"], "LEFT JOIN + GROUP BY", rad=-0.18)
    arrow(ax, emac["r"], evsm["l"], "(join makro)", rad=0.10)

    # analytical -> kpi (materialise)
    arrow(ax, etrend["r"], k1["l"], "")
    arrow(ax, edemo["r"], k2["l"], "materialise")
    arrow(ax, evsm["r"], k3["l"], "")
    arrow(ax, evsm["r"], k4["l"], "", rad=-0.15)

    # column captions
    for cx, cap in ((x1 + W / 2, "RAW (extract_load.py)"),
                    (x2 + W / 2, "PIVOT / UNPIVOT (SQL)"),
                    (x3 + W / 2, "ANALITIK (window / OLAP)"),
                    (x4 + kw / 2, "KPI (dashboard_kpis.sql)")):
        ax.text(cx, 9.2, cap, ha="center", fontsize=8, weight="bold", color="#334155")

    ax.text(8.5, 0.7,
            "Semua tabel STORED AS PARQUET (USING PARQUET).  Sumber: elt_pipeline/transform.sql "
            "+ warehouse/dashboard_kpis.sql.",
            ha="center", fontsize=7.3, color="#475569", style="italic")
    ax.text(8.5, 0.3,
            "Kontras dengan ETL: tidak ada PK/FK star schema — ini rantai tabel turunan set-based.",
            ha="center", fontsize=7.3, color="#475569", style="italic")

    fig.tight_layout()
    for ext in ("png", "pdf"):
        out = OUT_DIR / f"elt_lineage.{ext}"
        fig.savefig(out, bbox_inches="tight", dpi=160)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
