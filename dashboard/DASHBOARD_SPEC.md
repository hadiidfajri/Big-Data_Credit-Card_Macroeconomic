# Dashboard Specification — built identically in Tableau (ETL) & Power BI (ELT)

One design, two tools, two warehouses (CLAUDE.md §8). Tableau → `bigdata_etl`,
Power BI → `bigdata_elt`. Both read the same `kpi_*` tables, so the visuals and the
numbers can be compared side-by-side as evidence for the ETL-vs-ELT analysis (§9).

## Data sources (per tool)
| KPI table                         | Columns                                                                 |
|-----------------------------------|-------------------------------------------------------------------------|
| `kpi_overall`                     | `default_rate`, `total_clients`                                          |
| `kpi_default_by_demographic`      | `dimension`, `category`, `clients`, `default_rate`                       |
| `kpi_monthly_default_vs_macro`    | `date_key`, `month_name`, `default_rate`, `exchange_rate_twd_usd`, `real_broad_eer`, `total_reserves` |
| `kpi_corr_default_macro`          | `corr_fx`, `corr_reer`, `corr_reserves`                                  |

## Layout — single dashboard, 4 zones

### A. KPI header (cards) — *from `kpi_overall` + `kpi_corr_default_macro`*
- **Overall Default Rate** (big % card).
- **Total Clients** (count card).
- **Default↔FX / ↔Reserves correlation** (3 small cards from `kpi_corr_default_macro`).

### B. Default rate by demographic (distribution & comparison) — *`kpi_default_by_demographic`*
- Bar chart of `default_rate` by `category`, **filtered/faceted by `dimension`**
  (sex / education / marriage / age_band).
- Reference line at the overall default rate for quick comparison.

### C. Time-based trend (Apr–Sep 2005) — *`kpi_monthly_default_vs_macro`*
- Dual-axis line: `default_rate` vs a selectable macro indicator
  (`exchange_rate_twd_usd` / `real_broad_eer` / `total_reserves`) over `month_name`.
- Sort by `date_key` so months read Apr→Sep.

### D. Default vs macro (relationship) — *`kpi_monthly_default_vs_macro`*
- Scatter: x = chosen macro indicator, y = `default_rate`, one point per month,
  with a trend line; annotate the correlation from `kpi_corr_default_macro`.

## Required interactive filters
- **Demographic dimension** selector (sex / education / marriage / age_band) → zone B.
- **Macro indicator** selector (FX / real broad EER / reserves) → zones C & D.
- **Month** range (Apr–Sep 2005) → zones C & D.
- (Optional) **Default class** highlight (default vs non-default).

## Required elements checklist (§8)
- [x] KPIs — overall default rate, per-demographic default rate, default↔macro correlation.
- [x] Time-based trend analysis — zone C.
- [x] Distribution & comparison — zone B (bars) + zone D (scatter).
- [x] Interactive filters — dimension, macro indicator, month.

## Build notes
- Keep the **same field names, colours, and layout** in both tools so screenshots line up.
- Save artifacts: `dashboard/tableau_etl_dashboard.twbx`, `dashboard/powerbi_elt_dashboard.pbix`,
  and PNG exports in `dashboard/screenshots/` (used in the report §9 comparison).
- ⚠️ Honest scope: the `.twbx`/`.pbix` are assembled manually in the GUIs; this spec +
  the `kpi_*` tables + the ODBC guide are what the pipeline provides.
