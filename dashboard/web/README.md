# KPI website (ETL & ELT) — offline

`index.html` is a **self-contained** KPI dashboard for the credit-default analytics,
styled after the "Incident Report" card (dark rounded card, animated CountUp
numbers, stacked normalized area chart, trend badges, metric rows). It needs **no
web server, no Node, no internet** — just double-click `index.html`.

## What it shows
- **ETL / ELT toggle** (top-right select): switches between the `bigdata_etl`
  (ETL) and `bigdata_elt` (ELT) warehouse outputs. The KPIs are identical, which
  is itself evidence the two pipelines agree. This web page **is** the dashboard
  for both pipelines — visualization is **web-only** (no Power BI, no Tableau).
- **Main card:** macro-composition area chart (Apr–Sep 2005), defaulting vs
  non-defaulting client counts, and highest/lowest-risk-group + default↔macro
  metric rows.
- **Secondary cards:** default rate by demographic (sex / education / marriage /
  age_band selector, with overall reference line), macro-vs-default scatter
  (FX / REER / reserves selector), and a per-category detail table.

## Data source & regeneration
The page **embeds** the values from `dashboard/exports/bigdata_*__kpi_*.csv`
(produced by `export_kpis_csv.py`). To refresh after re-running the pipeline:

```bash
python dashboard/export_kpis_csv.py        # re-dump KPI tables -> exports/*.csv
python dashboard/build_web_dashboard.py    # rebuild web/index.html
```

`preview.png` is a static render of the page (for the report screenshots).
