"""Prompt 10 — render the data-flow architecture diagram (CLAUDE.md §5).

Draws the Sources → Kafka → raw/datalake → ETL/ELT → warehouse → BI flow with
matplotlib and saves both ``architecture_diagram.pdf`` (required deliverable) and
``architecture_diagram.png``.

Run::

    python architecture_diagram.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent

# palette
SRC, BUS, LAKE = "#cfe8ff", "#ffe0b2", "#e1bee7"
ETL, ELT, WH, BI = "#c8e6c9", "#b3e5fc", "#fff9c4", "#f8bbd0"


def box(ax, xy, w, h, text, color):
    x, y = xy
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=1.2, edgecolor="#444", facecolor=color))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5, wrap=True)
    return (x + w / 2, y)  # bottom-center anchor


def arrow(ax, p1, p2):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12,
                                 linewidth=1.1, color="#555",
                                 connectionstyle="arc3,rad=0.0"))


def main() -> int:
    fig, ax = plt.subplots(figsize=(11, 13))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 16)
    ax.axis("off")
    ax.set_title("Tugas Besar Big Data — ETL & ELT Architecture (data flow)",
                 fontsize=12, weight="bold")

    W, H = 4.2, 1.0
    cx = 4.0  # left column x
    rx = 7.5  # right column x

    # top: sources + kafka (centered)
    src = box(ax, (3.9, 14.3), W, H, "Sources\nUCI XLSX/CSV  +  FRED API/JSON (2005)", SRC)
    bus = box(ax, (3.9, 12.7), W, H,
              "Apache Kafka (KRaft)\nproducers → topics → consumers", BUS)
    arrow(ax, (6.0, 14.3), (6.0, 13.7))

    # split to raw / datalake
    raw = box(ax, (1.6, 11.0), 3.6, H, "raw/   (ETL landing)", LAKE)
    lake = box(ax, (6.6, 11.0), 3.6, H, "datalake/   (ELT landing)", LAKE)
    arrow(ax, (6.0, 12.7), (3.4, 12.0))
    arrow(ax, (6.0, 12.7), (8.4, 12.0))

    # ETL column (left)
    syn = box(ax, (cx - 2.1, 9.3), W, H, "synthetic/ CTGAN\n≥150k clients (pre-FRED merge)", ETL)
    etl_t = box(ax, (cx - 2.1, 7.6), W, H,
                "[ETL] Spark transform (PySpark)\nclean · IQR/Z · unpivot→monthly · 5 features · validate", ETL)
    etl_w = box(ax, (cx - 2.1, 5.9), W, H,
                "Hive star schema (bigdata_etl)\nfact_credit_monthly + dim_client/date/macro", WH)
    arrow(ax, (3.4, 11.0), (cx, 10.3))
    arrow(ax, (cx, 9.3), (cx, 8.6))
    arrow(ax, (cx, 7.6), (cx, 6.9))

    # ELT column (right)
    elt_r = box(ax, (rx - 2.1, 9.3), W, H,
                "[ELT] load raw → Hive raw tables\n(bigdata_elt.raw_credit / raw_macro)", ELT)
    elt_t = box(ax, (rx - 2.1, 7.6), W, H,
                "Hive / Spark SQL transform\nstack() unpivot · window funcs · GROUPING SETS OLAP", ELT)
    elt_w = box(ax, (rx - 2.1, 5.9), W, H,
                "Hive ELT tables (bigdata_elt)\nelt_fact_monthly + analytical tables", WH)
    arrow(ax, (8.4, 11.0), (rx, 10.3))
    arrow(ax, (rx, 9.3), (rx, 8.6))
    arrow(ax, (rx, 7.6), (rx, 6.9))

    # KPI layer + BI
    kpi = box(ax, (3.9, 4.2), W, H, "Dashboard KPI tables\nkpi_*  (same names in both DBs)", WH)
    arrow(ax, (cx, 5.9), (5.4, 5.2))
    arrow(ax, (rx, 5.9), (6.6, 5.2))

    tab = box(ax, (cx - 2.1, 2.5), W, H, "Tableau  (Hive ODBC)\n→ ETL output", BI)
    pbi = box(ax, (rx - 2.1, 2.5), W, H, "Power BI  (Hive ODBC)\n→ ELT output", BI)
    arrow(ax, (5.4, 4.2), (cx, 3.5))
    arrow(ax, (6.6, 4.2), (rx, 3.5))

    ax.text(6.0, 1.7, "Same dashboard design built in both tools (KPIs · trend · distribution · filters)",
            ha="center", fontsize=8.5, style="italic")
    ax.text(6.0, 1.2, "Deployment: Docker Compose — Kafka · Spark master+worker · Hive metastore + HiveServer2 · Postgres",
            ha="center", fontsize=7.5, color="#555")

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = REPO_ROOT / f"architecture_diagram.{ext}"
        fig.savefig(out, bbox_inches="tight", dpi=160)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
