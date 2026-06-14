"""Render the ETL warehouse **star schema (ERD)** as an image.

Central fact ``fact_credit_monthly`` surrounded by its dimensions
(``dim_client``, ``dim_date``, ``dim_macro``) with column data types and PK/FK
relationship lines, mirroring ``warehouse/etl_star_schema.sql``. Saves
``warehouse/erd_star_schema.png`` and ``.pdf``.

Run::  python warehouse/erd_diagram.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent

FACT_HEAD, FACT_BODY = "#fde68a", "#fffbeb"
DIM_HEAD, DIM_BODY = "#bbf7d0", "#f0fdf4"
PK_C, FK_C, TYPE_C = "#b91c1c", "#1d4ed8", "#6b7280"

# (column, TYPE, key)  key in {"PK","FK","PF"(both),""}
FACT = ("fact_credit_monthly", "grain: 1 baris / client x bulan (Apr-Sep 2005) - 900,000 baris", [
    ("id", "BIGINT", "FK"),
    ("date_key", "INT", "FK"),
    ("month", "INT", ""), ("month_name", "STRING", ""),
    ("limit_bal", "DOUBLE", ""), ("pay_status", "INT", ""),
    ("bill_amt", "DOUBLE", ""), ("pay_amt", "DOUBLE", ""),
    ("credit_utilization", "DOUBLE", ""),
    ("payment_ratio", "DOUBLE", ""),
    ("exchange_rate_twd_usd", "DOUBLE", ""),
    ("real_broad_eer", "DOUBLE", ""),
    ("nominal_broad_eer", "DOUBLE", ""),
    ("total_reserves", "DOUBLE", ""),
    ("default_payment_next_month", "INT", ""),
])
DIM_CLIENT = ("dim_client", "150,000 baris", [
    ("id", "BIGINT", "PK"),
    ("sex / sex_label", "INT/STR", ""),
    ("education / education_label", "INT/STR", ""),
    ("marriage / marriage_label", "INT/STR", ""),
    ("age / age_band", "INT/STR", ""),
    ("default_payment_next_month", "INT", ""),
    ("avg_delay_months", "DOUBLE", ""),
    ("num_months_delayed", "INT", ""),
    ("total_bill_amt", "DOUBLE", ""),
    ("total_pay_amt", "DOUBLE", ""),
    ("repayment_gap", "DOUBLE", ""),
])
DIM_DATE = ("dim_date", "12 baris (2005)", [
    ("date_key", "INT", "PK"),
    ("full_date", "DATE", ""), ("year", "INT", ""), ("month", "INT", ""),
    ("month_name", "STRING", ""), ("quarter", "INT", ""),
    ("is_billing_month", "BOOLEAN", ""),
])
DIM_MACRO = ("dim_macro", "12 baris - FRED Taiwan 2005", [
    ("date_key", "INT", "PF"),
    ("exchange_rate_twd_usd", "DOUBLE", ""),
    ("real_broad_eer", "DOUBLE", ""),
    ("nominal_broad_eer", "DOUBLE", ""),
    ("total_reserves", "DOUBLE", ""),
    ("exchange_rate_twd_usd_norm", "DOUBLE", ""),
    ("real_broad_eer_norm", "DOUBLE", ""),
    ("total_reserves_norm", "DOUBLE", ""),
])

ROW_H = 0.46
HEAD_H = 1.0


def table(ax, x, y, w, spec, head_color, body_color):
    name, grain, cols = spec
    total_h = HEAD_H + ROW_H * len(cols)
    top, bottom = y, y - (HEAD_H + ROW_H * len(cols))
    ax.add_patch(FancyBboxPatch((x, bottom), w, total_h,
                 boxstyle="round,pad=0.01,rounding_size=0.04",
                 linewidth=1.3, edgecolor="#334155", facecolor=body_color, zorder=2))
    ax.add_patch(FancyBboxPatch((x, top - HEAD_H), w, HEAD_H,
                 boxstyle="round,pad=0.01,rounding_size=0.04",
                 linewidth=1.3, edgecolor="#334155", facecolor=head_color, zorder=3))
    ax.text(x + w / 2, top - 0.4, name, ha="center", va="center",
            fontsize=10.5, weight="bold", zorder=4)
    ax.text(x + w / 2, top - 0.78, grain, ha="center", va="center",
            fontsize=6.6, style="italic", color="#475569", zorder=4)

    anchors = {}
    for i, (col, typ, key) in enumerate(cols):
        ry = top - HEAD_H - ROW_H * (i + 0.5)
        lead = ""
        if key in ("PK", "PF"):
            ax.text(x + 0.12, ry, "PK", ha="left", va="center", fontsize=6.2,
                    weight="bold", color=PK_C, zorder=4)
            lead = "      "
        elif key == "FK":
            ax.text(x + 0.12, ry, "FK", ha="left", va="center", fontsize=6.2,
                    weight="bold", color=FK_C, zorder=4)
            lead = "      "
        ax.text(x + 0.12, ry, lead + col, ha="left", va="center", fontsize=7.2, zorder=4)
        ax.text(x + w - 0.12, ry, typ, ha="right", va="center", fontsize=6.3,
                color=TYPE_C, zorder=4)
        if key == "PF":  # extra FK marker line under the PK label handled by relation
            pass
        if i < len(cols) - 1:
            ax.plot([x + 0.06, x + w - 0.06], [top - HEAD_H - ROW_H * (i + 1)] * 2,
                    color="#e2e8f0", linewidth=0.5, zorder=3)
        anchors[col] = ry
    return {"x": x, "w": w, "top": top, "bottom": bottom,
            "left": x, "right": x + w, "rows": anchors}


def rel(ax, p1, p2, label):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=14,
                 linewidth=1.6, color="#0f3d63", connectionstyle="arc3,rad=0.0", zorder=1))
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    ax.text(mx, my + 0.2, label, ha="center", va="center", fontsize=6.6,
            color="#0f3d63", weight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85), zorder=5)


def main() -> int:
    fig, ax = plt.subplots(figsize=(16, 10.5))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis("off")
    ax.set_title("ETL Warehouse — Star Schema / ERD (bigdata_etl)",
                 fontsize=14, weight="bold")

    fact = table(ax, 6.0, 9.6, 4.2, FACT, FACT_HEAD, FACT_BODY)
    dclient = table(ax, 0.4, 8.4, 3.9, DIM_CLIENT, DIM_HEAD, DIM_BODY)
    ddate = table(ax, 12.1, 10.6, 3.6, DIM_DATE, DIM_HEAD, DIM_BODY)
    dmacro = table(ax, 12.1, 6.0, 3.6, DIM_MACRO, DIM_HEAD, DIM_BODY)

    rel(ax, (dclient["right"], dclient["rows"]["id"]),
        (fact["left"], fact["rows"]["id"]), "1 : N")
    rel(ax, (ddate["left"], ddate["rows"]["date_key"]),
        (fact["right"], fact["rows"]["date_key"]), "1 : N")
    rel(ax, (dmacro["left"], dmacro["rows"]["date_key"]),
        (fact["right"], fact["rows"]["date_key"]), "1 : N")
    rel(ax, ((ddate["left"] + ddate["right"]) / 2, ddate["bottom"]),
        ((dmacro["left"] + dmacro["right"]) / 2, dmacro["top"]), "date_key")

    # legend
    ax.text(0.4, 0.7,
            "PK = Primary Key   FK = Foreign Key   PF = PK & FK   |   semua tabel STORED AS PARQUET",
            ha="left", fontsize=7.5, color=PK_C)
    ax.text(0.4, 0.35,
            "Tipe data & kolom: warehouse/etl_star_schema.sql   |   1:N = satu dimensi -> banyak baris fakta",
            ha="left", fontsize=7.5, color="#475569", style="italic")

    fig.tight_layout()
    for ext in ("png", "pdf"):
        out = OUT_DIR / f"erd_star_schema.{ext}"
        fig.savefig(out, bbox_inches="tight", dpi=160)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
