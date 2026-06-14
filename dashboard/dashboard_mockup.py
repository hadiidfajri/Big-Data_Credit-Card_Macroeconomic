"""Render a VISUAL PREVIEW of the analytics dashboard (4 zones) from the documented
KPI numbers — a stand-in for the Tableau/Power BI screenshots until those GUI tools
are built. NOT a live screenshot; values come from the documented run (report.pdf §6.3,
docs/PROSES_ETL_ELT) and real FRED EXTAUS monthly rates.

Run::  python dashboard/dashboard_mockup.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent / "screenshots"

# --- documented KPI values -------------------------------------------------- #
OVERALL = 0.2212
TOTAL_CLIENTS = 150_000
CORR_FX = CORR_REER = CORR_RES = 0.00

# highest-risk category per demographic dimension (documented extremes)
DEMO = [("Perempuan\n(sex)", 0.2439), ("University\n(edu)", 0.2504),
        ("Married\n(marriage)", 0.2661), ("40-49\n(age)", 0.2451)]

MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
FX = [31.48, 31.27, 31.35, 31.89, 32.08, 32.92]      # real FRED EXTAUS Apr-Sep 2005
DEF_RATE = [OVERALL] * 6                                # constant (client-level label)

NAVY, GREEN, AMBER, RED = "#1d4ed8", "#16a34a", "#d97706", "#b91c1c"


def card(ax, x, w, title, value, color):
    ax.add_patch(FancyBboxPatch((x, 0.12), w, 0.76, boxstyle="round,pad=0.02,rounding_size=0.04",
                 linewidth=1.2, edgecolor=color, facecolor="white"))
    ax.add_patch(FancyBboxPatch((x, 0.74), w, 0.14, boxstyle="square,pad=0",
                 linewidth=0, facecolor=color))
    ax.text(x + w / 2, 0.81, title, ha="center", va="center", color="white",
            fontsize=8.5, weight="bold")
    ax.text(x + w / 2, 0.44, value, ha="center", va="center", color=color,
            fontsize=20, weight="bold")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(14, 9))
    fig.suptitle("Dashboard — Credit-Card Default Risk Taiwan (2005)  vs  Macro",
                 fontsize=15, weight="bold", y=0.985)
    gs = fig.add_gridspec(3, 2, height_ratios=[0.62, 1, 1], hspace=0.42, wspace=0.22,
                          left=0.07, right=0.96, top=0.92, bottom=0.07)

    # ---- Zona A: KPI cards ----
    axc = fig.add_subplot(gs[0, :]); axc.axis("off"); axc.set_xlim(0, 1); axc.set_ylim(0, 1)
    card(axc, 0.00, 0.225, "Overall Default Rate", f"{OVERALL*100:.2f}%", RED)
    card(axc, 0.258, 0.225, "Total Clients", f"{TOTAL_CLIENTS:,}", NAVY)
    card(axc, 0.516, 0.225, "Highest-risk group", "Married 26.6%", AMBER)
    card(axc, 0.775, 0.225, "Default vs Macro corr", f"{CORR_FX:.2f}", GREEN)

    # ---- Zona B: default rate per demografi (bar + reference line) ----
    axb = fig.add_subplot(gs[1, 0])
    labels = [d[0] for d in DEMO]; vals = [d[1] for d in DEMO]
    bars = axb.bar(labels, vals, color=["#60a5fa", "#34d399", "#fbbf24", "#f87171"])
    axb.axhline(OVERALL, color=RED, linestyle="--", linewidth=1.2)
    axb.text(3.4, OVERALL + 0.004, f"overall {OVERALL:.3f}", color=RED, fontsize=7.5, ha="right")
    for b, v in zip(bars, vals):
        axb.text(b.get_x() + b.get_width() / 2, v + 0.004, f"{v:.3f}", ha="center", fontsize=8)
    axb.set_title("B. Default rate — kategori berisiko tertinggi / dimensi", fontsize=10, weight="bold")
    axb.set_ylabel("default rate"); axb.set_ylim(0, 0.32)
    axb.spines[["top", "right"]].set_visible(False)

    # ---- Zona C: tren bulanan (dual axis: default rate vs FX) ----
    axt = fig.add_subplot(gs[1, 1])
    l1 = axt.plot(MONTHS, DEF_RATE, "-o", color=RED, label="default rate")[0]
    axt.set_ylabel("default rate", color=RED); axt.set_ylim(0, 0.30)
    axt.tick_params(axis="y", labelcolor=RED)
    axt2 = axt.twinx()
    l2 = axt2.plot(MONTHS, FX, "-s", color=NAVY, label="kurs TWD/USD")[0]
    axt2.set_ylabel("TWD/USD (EXTAUS)", color=NAVY)
    axt2.tick_params(axis="y", labelcolor=NAVY)
    axt.set_title("C. Tren bulanan Apr–Sep 2005: default vs kurs", fontsize=10, weight="bold")
    axt.legend(handles=[l1, l2], loc="upper left", fontsize=7.5)

    # ---- Zona D: scatter default vs makro (corr ~ 0) ----
    axs = fig.add_subplot(gs[2, 0])
    axs.scatter(FX, DEF_RATE, color=NAVY, s=60, zorder=3)
    axs.set_xlabel("kurs TWD/USD"); axs.set_ylabel("default rate")
    axs.set_ylim(0.18, 0.26)
    axs.set_title("D. Default vs kurs (korelasi ≈ 0)", fontsize=10, weight="bold")
    axs.text(0.5, 0.5, "korelasi ≈ 0.00", transform=axs.transAxes, ha="center",
             color=GREEN, fontsize=11, weight="bold")
    axs.spines[["top", "right"]].set_visible(False)

    # ---- Notes panel ----
    axn = fig.add_subplot(gs[2, 1]); axn.axis("off")
    axn.text(0.0, 0.95, "Catatan & filter interaktif (di Tableau/Power BI):", fontsize=9.5,
             weight="bold", va="top")
    notes = [
        "• Filter: dimensi demografi · indikator makro · rentang bulan",
        "• Tableau -> sumber ETL (bigdata_etl); Power BI -> ELT (bigdata_elt)",
        "• Korelasi default↔makro = 0 karena label default bersifat per-klien",
        "  (konstan tiap bulan) — keterbatasan grain, lihat report §10.",
        "• Sumber angka: report.pdf §6.3 + FRED EXTAUS (kurs nyata Apr–Sep 2005).",
    ]
    for i, t in enumerate(notes):
        axn.text(0.0, 0.80 - i * 0.14, t, fontsize=8.2, va="top")

    fig.text(0.5, 0.012,
             "PREVIEW dibuat dari KPI terdokumentasi (dashboard/dashboard_mockup.py) — "
             "bukan screenshot langsung Tableau/Power BI.",
             ha="center", fontsize=7.5, color="#6b7280", style="italic")

    for ext in ("png", "pdf"):
        out = OUT / f"dashboard_preview.{ext}"
        fig.savefig(out, bbox_inches="tight", dpi=150)
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
