"""Build a self-contained KPI website (ETL + ELT) from the exported CSVs.

Reads the eight ``dashboard/exports/bigdata_{etl,elt}__kpi_*.csv`` files (produced
by ``export_kpis_csv.py``) and renders a single **offline** HTML page
(``dashboard/web/index.html``) styled after the "Incident Report" dashboard card
(dark rounded card + layered shadow, animated CountUp numbers, stacked normalized
area chart, trend badges, metric rows) — all with inline SVG/CSS/JS, no external
libraries, no web server, no CORS. It opens by double-clicking the file.

An ETL / ELT toggle switches between the ``bigdata_etl`` (ETL) and ``bigdata_elt``
(ELT) warehouse outputs (the KPIs are identical, which is itself evidence that both
pipelines agree). Visualisation is web-only — no Power BI, no Tableau.

Run::

    python dashboard/build_web_dashboard.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
EXPORTS = BASE / "exports"
OUT = BASE / "web" / "index.html"

AGE_ORDER = {"<30": 0, "30-39": 1, "40-49": 2, "50-59": 3, "60+": 4}


def read_csv(name: str) -> list[dict]:
    path = EXPORTS / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(x):
    try:
        f = float(x)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return x


def build_side(db: str) -> dict:
    overall_rows = read_csv(f"{db}__kpi_overall.csv")
    corr_rows = read_csv(f"{db}__kpi_corr_default_macro.csv")
    demo_rows = read_csv(f"{db}__kpi_default_by_demographic.csv")
    monthly_rows = read_csv(f"{db}__kpi_monthly_default_vs_macro.csv")

    overall = {k: num(v) for k, v in (overall_rows[0] if overall_rows else {}).items()}
    corr = {k: num(v) for k, v in (corr_rows[0] if corr_rows else {}).items()}

    demo: dict[str, list] = {}
    for r in demo_rows:
        demo.setdefault(r["dimension"], []).append(
            {"category": r["category"], "clients": num(r["clients"]),
             "default_rate": num(r["default_rate"])})
    for dim, items in demo.items():
        if dim == "age_band":
            items.sort(key=lambda i: AGE_ORDER.get(i["category"], 99))
        else:
            items.sort(key=lambda i: i["default_rate"], reverse=True)

    monthly = sorted(
        [{"date_key": num(r["date_key"]), "month_name": r["month_name"],
          "default_rate": num(r["default_rate"]),
          "exchange_rate_twd_usd": num(r["exchange_rate_twd_usd"]),
          "real_broad_eer": num(r["real_broad_eer"]),
          "total_reserves": num(r["total_reserves"])} for r in monthly_rows],
        key=lambda r: r["date_key"])

    return {"overall": overall, "corr": corr, "demo": demo, "monthly": monthly}


def main() -> int:
    data = {"etl": build_side("bigdata_etl"), "elt": build_side("bigdata_elt")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = (HTML_TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__GENERATED__", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(BASE.parent)}  "
          f"(etl months={len(data['etl']['monthly'])}, dims={list(data['etl']['demo'])})")
    return 0


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Credit Default Report — KPI (ETL &amp; ELT)</title>
<style>
  :root{
    --page:#1f2937; --card:#000; --card2:#0c0c12; --ink:#fff; --muted:#9ca3af;
    --div:#262631; --field:#262631;
    --c1:#FAE5F6; --c2:#EE4094; --c3:#BB015A;
    --red:#F08083; --redbg:rgba(232,64,69,.40); --teal:#40E5D1; --tealbg:rgba(64,229,209,.40);
    --etl:#38bdf8; --elt:#a78bfa;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--page);color:var(--ink);
    font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
    display:flex;flex-direction:column;align-items:center;padding:32px 16px 48px}
  .mono{font-family:ui-monospace,'SFMono-Regular',Consolas,'Liberation Mono',monospace}
  h1.page{font-size:18px;font-weight:600;margin:0 0 18px;color:#e5e7eb;letter-spacing:.01em}
  h1.page span{color:var(--muted);font-weight:400;font-size:14px}

  .card{background:var(--card);border-radius:24px;width:100%;max-width:680px;overflow:hidden;
    transition:colors .3s;
    box-shadow:11px 21px 3px rgba(0,0,0,0.06),14px 27px 7px rgba(0,0,0,0.10),
      19px 38px 14px rgba(0,0,0,0.13),27px 54px 27px rgba(0,0,0,0.16),
      39px 78px 50px rgba(0,0,0,0.20),55px 110px 86px rgba(0,0,0,0.26);
    padding:16px 0;margin-bottom:26px}
  .head{display:flex;justify-content:space-between;align-items:center;padding:10px 28px 26px}
  .head h3{font-size:28px;font-weight:700;margin:0}
  select{background:var(--field);color:#fff;border:0;padding:10px 12px;border-radius:8px;font-size:14px;cursor:pointer;outline:none}
  select:focus{box-shadow:0 0 0 2px #3b82f6}

  .legend{display:flex;gap:28px;padding:0 32px 14px;flex-wrap:wrap}
  .legend .it{display:flex;gap:8px;align-items:center}
  .legend .sw{width:16px;height:16px;border-radius:3px}
  .legend span{color:var(--muted);font-size:12px}

  .chart{padding:0 10px}
  .tick{fill:#9A9AAF;font-size:11px}
  .grid{stroke:rgba(126,126,143,.30);stroke-width:1}

  .stats{display:flex;flex-wrap:wrap;gap:16px;padding:26px 32px 6px;justify-content:space-between}
  .stat{display:flex;flex-direction:column;gap:8px;min-width:230px;flex:1}
  .stat .t{font-size:20px;color:#e5e7eb}
  .stat .row{display:flex;align-items:center;gap:10px}
  .stat .num{font-size:38px;font-weight:600}
  .pill{display:inline-flex;align-items:center;gap:3px;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600}
  .pill.up{color:var(--red);background:var(--redbg)}
  .pill.down{color:var(--teal);background:var(--tealbg)}
  .stat .cmp{font-size:13px;color:var(--muted)}

  .metrics{padding:8px 32px 6px;margin-top:8px}
  .metric{display:flex;align-items:center;gap:8px;padding:16px 0;border-top:1px solid var(--div)}
  .metric:first-child{border-top:0}
  .metric .l{display:flex;gap:8px;align-items:center;width:55%;color:var(--muted);font-size:15px}
  .metric .l .lab{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .metric .r{display:flex;gap:10px;align-items:center;justify-content:flex-end;width:45%}
  .metric .val{font-size:19px;font-weight:600;color:#fff}

  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px;width:100%;max-width:680px}
  @media(max-width:720px){.grid2{grid-template-columns:1fr}.stats{flex-direction:column}}
  .sub{background:var(--card2);border-radius:18px;padding:16px 18px;
    box-shadow:0 10px 30px rgba(0,0,0,.45)}
  .sub h4{margin:0 0 2px;font-size:14px}
  .sub .d{color:var(--muted);font-size:12px;margin-bottom:8px}
  .ctrlrow{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
  .ctrlrow select{padding:7px 9px;font-size:12px}
  .refline{stroke:#fbbf24;stroke-width:1.4;stroke-dasharray:5 4}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th{color:var(--muted);text-align:left;font-weight:500;padding:6px 4px}
  td{padding:6px 4px;border-top:1px solid var(--div)}
  .insight{width:100%;max-width:680px;margin-top:22px;background:var(--card2);
    border-left:4px solid var(--c2);border-radius:12px;padding:14px 18px;
    font-size:13px;line-height:1.6;color:#cbd5e1}
  .insight b{color:#fff}
  footer{color:var(--muted);font-size:11.5px;margin-top:22px;max-width:680px;text-align:center;line-height:1.6}
  code{color:#cbd5e1}
</style>
</head>
<body>
  <h1 class="page">Credit Default Risk — Taiwan 2005 &nbsp;<span>· KPI dashboard over the Hive warehouse · ETL &amp; ELT</span></h1>

  <!-- ===================== MAIN REPORT CARD ===================== -->
  <div class="card">
    <div class="head">
      <h3>Default Report</h3>
      <select id="sideSel" aria-label="Pipeline / warehouse">
        <option value="etl">ETL · bigdata_etl</option>
        <option value="elt">ELT · bigdata_elt</option>
      </select>
    </div>

    <div class="legend" id="legend"></div>
    <div class="d" style="padding:0 32px 10px;color:#9ca3af;font-size:11px">Monthly composition of macro indicators — each min–max scaled across Apr–Sep, then normalized to 100%.</div>

    <div class="chart"><div id="areaChart"></div></div>

    <div class="stats" id="stats"></div>

    <div class="metrics mono" id="metrics"></div>
  </div>

  <!-- ===================== SECONDARY CARDS ===================== -->
  <div class="grid2">
    <div class="sub">
      <div class="ctrlrow"><h4>Default rate by demographic</h4>
        <select id="dimSel" aria-label="Demographic dimension"></select></div>
      <div class="d" id="barDesc"></div>
      <div id="barChart"></div>
    </div>
    <div class="sub">
      <div class="ctrlrow"><h4>Macro vs default rate</h4>
        <select id="macroSel" aria-label="Macro indicator">
          <option value="exchange_rate_twd_usd">Exchange rate (TWD/USD)</option>
          <option value="real_broad_eer">Real broad EER</option>
          <option value="total_reserves">Total reserves</option>
        </select></div>
      <div class="d" id="scatterDesc"></div>
      <div id="scatter"></div>
    </div>
    <div class="sub" style="grid-column:1/-1">
      <h4>Per-category detail (<span id="detDim"></span>)</h4>
      <div class="d">Orange dashed = overall default rate; pp = percentage points vs overall.</div>
      <div id="tableWrap"></div>
    </div>
  </div>

  <div class="insight" id="insight"></div>
  <footer>
    Source: <code>dashboard/exports/bigdata_{etl,elt}__kpi_*.csv</code> ·
    ETL star schema vs ELT in-warehouse SQL · styled after the "Incident Report" card ·
    offline static page (inline SVG, no dependencies) · generated __GENERATED__
  </footer>

<script>
const DATA = __DATA__;
const PALETTE = ["#FAE5F6","#EE4094","#BB015A"];
const MACROS = [
  {key:"exchange_rate_twd_usd", label:"Exchange rate (TWD/USD)"},
  {key:"real_broad_eer",        label:"Real broad EER"},
  {key:"total_reserves",        label:"Total reserves"},
];
const MACRO_LABEL = Object.fromEntries(MACROS.map(m=>[m.key,m.label]));
const state = {side:"etl", dim:"sex", macro:"exchange_rate_twd_usd"};
const SVGNS="http://www.w3.org/2000/svg";
const pct = v => (v*100).toFixed(2)+"%";
const fmtInt = v => Number(Math.round(v)).toLocaleString("en-US");
const fmtNum = v => Number(v).toLocaleString("en-US",{maximumFractionDigits:2});
function E(t,a={},txt){const e=document.createElementNS(SVGNS,t);for(const k in a)e.setAttribute(k,a[k]);if(txt!=null)e.textContent=txt;return e;}
function newSvg(w,h){return E("svg",{viewBox:`0 0 ${w} ${h}`,preserveAspectRatio:"xMidYMid meet",style:`width:100%;height:auto;display:block`});}

/* ---- inline icons (from the source component) ---- */
const IC = {
  diamond:'<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M9.92844 1.25411C9.32947 1.25895 8.73263 1.49041 8.28293 1.94747L1.92062 8.41475C1.02123 9.32885 1.03336 10.8178 1.94748 11.7172L8.41476 18.0795C9.32886 18.9789 10.8178 18.9667 11.7172 18.0526L18.0795 11.5861C18.979 10.6708 18.9667 9.18232 18.0526 8.28291L11.5853 1.92061C11.1283 1.47091 10.5274 1.24926 9.92844 1.25411ZM9.99028 5.40775C10.0739 5.40645 10.1569 5.42192 10.2344 5.45326C10.3119 5.48459 10.3823 5.53115 10.4415 5.59019C10.5006 5.64922 10.5474 5.71952 10.5789 5.79694C10.6105 5.87435 10.6261 5.95731 10.625 6.04089V11.0409C10.6262 11.1237 10.6109 11.2059 10.58 11.2828C10.5492 11.3596 10.5033 11.4296 10.4451 11.4886C10.387 11.5476 10.3177 11.5944 10.2413 11.6264C10.1649 11.6583 10.0829 11.6748 10 11.6748C9.91722 11.6748 9.83522 11.6583 9.75881 11.6264C9.6824 11.5944 9.6131 11.5476 9.55495 11.4886C9.4968 11.4296 9.45095 11.3596 9.42006 11.2828C9.38918 11.2059 9.37388 11.1237 9.37505 11.0409V6.04089C9.37289 5.87541 9.43645 5.71583 9.55178 5.59714C9.66711 5.47845 9.82481 5.41034 9.99028 5.40775ZM10 12.9159C10.2211 12.9159 10.433 13.0037 10.5893 13.16C10.7456 13.3162 10.8334 13.5282 10.8334 13.7492C10.8334 13.9702 10.7456 14.1822 10.5893 14.3385C10.433 14.4948 10.2211 14.5826 10 14.5826C9.77904 14.5826 9.56707 14.4948 9.41079 14.3385C9.25451 14.1822 9.16672 13.9702 9.16672 13.7492C9.16672 13.5282 9.25451 13.3162 9.41079 13.16C9.56707 13.0037 9.77904 12.9159 10 12.9159Z" fill="FILL"/></svg>',
  circle:'<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10.0001 1.66663C5.40511 1.66663 1.66675 5.40499 1.66675 9.99996C1.66675 14.5949 5.40511 18.3333 10.0001 18.3333C14.5951 18.3333 18.3334 14.5949 18.3334 9.99996C18.3334 5.40499 14.5951 1.66663 10.0001 1.66663ZM10.0001 2.91663C13.9195 2.91663 17.0834 6.08054 17.0834 9.99996C17.0834 13.9194 13.9195 17.0833 10.0001 17.0833C6.08066 17.0833 2.91675 13.9194 2.91675 9.99996C2.91675 6.08054 6.08066 2.91663 10.0001 2.91663ZM9.99032 5.82434C10.0740 5.82303 10.1570 5.83853 10.2346 5.86992C10.3121 5.90130 10.3826 5.94794 10.4418 6.00706C10.5010 6.06618 10.5477 6.13658 10.5792 6.21409C10.6107 6.29160 10.6263 6.37464 10.6251 6.45829V10.625C10.6263 10.7078 10.6110 10.79 10.5801 10.8669C10.5492 10.9437 10.5033 11.0137 10.4452 11.0726C10.387 11.1316 10.3177 11.1785 10.2413 11.2104C10.1649 11.2424 10.0829 11.2589 10.0001 11.2589C9.91725 11.2589 9.83525 11.2424 9.75884 11.2104C9.68243 11.1785 9.61313 11.1316 9.55498 11.0726C9.49683 11.0137 9.45098 10.9437 9.42009 10.8669C9.38921 10.79 9.37391 10.7078 9.37508 10.625V6.45829C9.37271 6.29267 9.43616 6.13288 9.55152 6.01401C9.66688 5.89515 9.82470 5.82693 9.99032 5.82434ZM10.0001 12.5C10.2211 12.5 10.4331 12.5878 10.5893 12.7440C10.7456 12.9003 10.8334 13.1123 10.8334 13.3333C10.8334 13.5543 10.7456 13.7663 10.5893 13.9225C10.4331 14.0788 10.2211 14.1666 10.0001 14.1666C9.77907 14.1666 9.56711 14.0788 9.41083 13.9225C9.25455 13.7663 9.16675 13.5543 9.16675 13.3333C9.16675 13.1123 9.25455 12.9003 9.41083 12.7440C9.56711 12.5878 9.77907 12.5 10.0001 12.5Z" fill="FILL"/></svg>',
  triangle:'<svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10.0001 2.10535C9.35241 2.10535 8.70472 2.42118 8.35459 3.05343L1.90440 14.7063C1.22414 15.9354 2.14514 17.5000 3.54990 17.5000H16.4511C17.8559 17.5000 18.7769 15.9354 18.0966 14.7063L11.6456 3.05343C11.2955 2.42118 10.6478 2.10535 10.0001 2.10535ZM9.99033 6.65776C10.0740 6.65645 10.1570 6.67195 10.2346 6.70333C10.3121 6.73472 10.3826 6.78135 10.4418 6.84047C10.5010 6.89959 10.5477 6.96999 10.5792 7.04750C10.6107 7.12501 10.6263 7.20806 10.6251 7.29171V11.4584C10.6263 11.5412 10.6110 11.6234 10.5801 11.7003C10.5492 11.7771 10.5034 11.8471 10.4452 11.9061C10.3870 11.9650 10.3178 12.0119 10.2413 12.0438C10.1649 12.0758 10.0829 12.0923 10.0001 12.0923C9.91727 12.0923 9.83527 12.0758 9.75886 12.0438C9.68245 12.0119 9.61315 11.9650 9.55500 11.9061C9.49685 11.8471 9.45100 11.7771 9.42011 11.7003C9.38923 11.6234 9.37393 11.5412 9.37510 11.4584V7.29171C9.37272 7.12609 9.43618 6.96629 9.55154 6.84743C9.66690 6.72856 9.82472 6.66034 9.99033 6.65776ZM10.0001 13.3334C10.2211 13.3334 10.4331 13.4212 10.5894 13.5775C10.7456 13.7337 10.8334 13.9457 10.8334 14.1667C10.8334 14.3877 10.7456 14.5997 10.5894 14.7560C10.4331 14.9122 10.2211 15.0000 10.0001 15.0000C9.77909 15.0000 9.56712 14.9122 9.41084 14.7560C9.25456 14.5997 9.16677 14.3877 9.16677 14.1667C9.16677 13.9457 9.25456 13.7337 9.41084 13.5775C9.56712 13.4212 9.77909 13.3334 10.0001 13.3334Z" fill="FILL"/></svg>',
  trendUp:(base,stroke)=>`<svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="14" fill="${base}" fill-opacity="0.4"/><path d="M9.50134 12.6111L14.0013 8.16663M14.0013 8.16663L18.5013 12.6111M14.0013 8.16663L14.0013 19.8333" stroke="${stroke}" stroke-width="2" stroke-linecap="square"/></svg>`,
  trendDown:(base,stroke)=>`<svg width="28" height="28" viewBox="0 0 28 28" fill="none"><rect width="28" height="28" rx="14" fill="${base}" fill-opacity="0.4"/><path d="M18.4987 15.3889L13.9987 19.8334M13.9987 19.8334L9.49866 15.3889M13.9987 19.8334V8.16671" stroke="${stroke}" stroke-width="2" stroke-linecap="square"/></svg>`,
  arrUp:s=>`<svg width="18" height="19" viewBox="0 0 20 21" fill="none"><path d="M5.50134 9.11119L10.0013 4.66675M10.0013 4.66675L14.5013 9.11119M10.0013 4.66675L10.0013 16.3334" stroke="${s}" stroke-width="2" stroke-linecap="square"/></svg>`,
  arrDown:s=>`<svg width="18" height="19" viewBox="0 0 20 21" fill="none"><path d="M14.4987 11.8888L9.99866 16.3333M9.99866 16.3333L5.49866 11.8888M9.99866 16.3333V4.66658" stroke="${s}" stroke-width="2" stroke-linecap="square"/></svg>`,
};
const icon=(name,fill)=>IC[name].replace("FILL",fill);

/* ---- CountUp ---- */
function countUp(node, end, fmt, dur=1800){
  node.textContent=fmt(end);   // final value first (correct even without animation)
  if(matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const start=performance.now();
  function step(t){
    const p=Math.min(1,(t-start)/dur), e=1-Math.pow(1-p,3);
    node.textContent=fmt(end*e);
    if(p<1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ---- stacked normalized area (macros over months) ---- */
function renderArea(){
  const rows=DATA[state.side].monthly;
  const keys=MACROS.map(m=>m.key);
  const W=640,H=280,m={t:14,r:16,b:34,l:16};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const xs=i=> m.l + (rows.length<2? iw/2 : iw*i/(rows.length-1));
  const yy=v=> m.t + ih*(1-v);   // v in [0,1]
  // min-max scale each macro across the months so the three (very different
  // magnitude) series are comparable, then show each month's normalized share.
  const ext={}; keys.forEach(k=>{const vs=rows.map(r=>r[k]); ext[k]=[Math.min(...vs),Math.max(...vs)];});
  const scaled=rows.map(r=>{const o={}; keys.forEach(k=>{const a=ext[k][0],b=ext[k][1]; o[k]=0.18+0.82*((r[k]-a)/((b-a)||1));}); return o;});
  const s=newSvg(W,H);
  // gridlines
  for(let k=0;k<=4;k++){const y=m.t+ih*k/4;s.appendChild(E("line",{class:"grid",x1:m.l,y1:y,x2:m.l+iw,y2:y}));}
  // gradients
  const defs=E("defs");
  PALETTE.forEach((c,i)=>{
    const g=E("linearGradient",{id:"g"+i,x1:0,y1:0,x2:0,y2:1});
    g.appendChild(E("stop",{offset:"0%","stop-color":c,"stop-opacity":0.85}));
    g.appendChild(E("stop",{offset:"80%","stop-color":c,"stop-opacity":0.25}));
    g.appendChild(E("stop",{offset:"100%","stop-color":c,"stop-opacity":0.05}));
    defs.appendChild(g);
  });
  s.appendChild(defs);
  // per-month normalized shares + cumulative boundaries
  const cum=rows.map(()=>0);
  keys.forEach((key,ki)=>{
    const lower=rows.map((r,i)=>cum[i]);
    rows.forEach((r,i)=>{
      const tot=keys.reduce((a,k)=>a+scaled[i][k],0)||1;
      cum[i]+= scaled[i][key]/tot;
    });
    const upper=rows.map((r,i)=>cum[i]);
    let d="M"+xs(0)+" "+yy(upper[0]);
    for(let i=1;i<rows.length;i++) d+=" L"+xs(i)+" "+yy(upper[i]);
    for(let i=rows.length-1;i>=0;i--) d+=" L"+xs(i)+" "+yy(lower[i]);
    d+=" Z";
    s.appendChild(E("path",{d, fill:"url(#g"+ki+")"}));
    // top line with glow
    let ld="M"+xs(0)+" "+yy(upper[0]);
    for(let i=1;i<rows.length;i++) ld+=" L"+xs(i)+" "+yy(upper[i]);
    s.appendChild(E("path",{d:ld, fill:"none", stroke:PALETTE[ki], "stroke-width":3, "stroke-linejoin":"round","stroke-linecap":"round"}));
  });
  // x labels (anchor first/last inward so they don't clip)
  rows.forEach((r,i)=>{const anc=i===0?"start":(i===rows.length-1?"end":"middle");
    s.appendChild(E("text",{class:"tick",x:xs(i),y:m.t+ih+18,"text-anchor":anc}, r.month_name));});
  const host=document.getElementById("areaChart");host.innerHTML="";host.appendChild(s);
}

function renderLegend(){
  document.getElementById("legend").innerHTML = MACROS.map((mm,i)=>
    `<div class="it"><span class="sw" style="background:${PALETTE[i]}"></span><span>${mm.label}</span></div>`).join("");
}

function renderStats(){
  const d=DATA[state.side], tot=d.overall.total_clients, rate=d.overall.default_rate;
  const def=tot*rate, nondef=tot*(1-rate);
  document.getElementById("stats").innerHTML=`
    <div class="stat">
      <span class="t">Defaulting clients</span>
      <div class="row"><span class="num mono" id="s1">0</span>
        <span class="pill up">${IC.arrUp("#F08083")}${(rate*100).toFixed(2)}%</span></div>
      <span class="cmp">of ${fmtInt(tot)} total clients</span>
    </div>
    <div class="stat">
      <span class="t">Non-defaulting clients</span>
      <div class="row"><span class="num mono" id="s2">0</span>
        <span class="pill down">${IC.arrDown("#40E5D1")}${((1-rate)*100).toFixed(2)}%</span></div>
      <span class="cmp">repay on time next month</span>
    </div>`;
  countUp(document.getElementById("s1"), def, fmtInt);
  countUp(document.getElementById("s2"), nondef, fmtInt);
}

function allCats(d){
  const out=[];
  for(const dim in d.demo) d.demo[dim].forEach(i=>{ if(i.category!=="unknown") out.push({dim,...i}); });
  return out;
}

function renderMetrics(){
  const d=DATA[state.side], cats=allCats(d);
  const hi=cats.slice().sort((a,b)=>b.default_rate-a.default_rate)[0];
  const lo=cats.slice().sort((a,b)=>a.default_rate-b.default_rate)[0];
  const corr=Number(d.corr.corr_fx).toFixed(3);
  const rows=[
    {ic:"diamond",fill:"#E84045",lab:"Highest-risk group",val:`${hi.dim}: ${hi.category} · ${pct(hi.default_rate)}`,trend:"up",base:"#E84045",stroke:"#F08083"},
    {ic:"circle",fill:"#E84045",lab:"Lowest-risk group",val:`${lo.dim}: ${lo.category} · ${pct(lo.default_rate)}`,trend:"down",base:"#40E5D1",stroke:"#40E5D1"},
    {ic:"triangle",fill:"#E84045",lab:"Default ↔ macro correlation",val:`r = ${corr}`,trend:"down",base:"#40E5D1",stroke:"#40E5D1"},
  ];
  document.getElementById("metrics").innerHTML = rows.map((r,idx)=>`
    <div class="metric" style="animation:fade .5s ease ${idx*0.06}s both">
      <div class="l">${icon(r.ic,r.fill)}<span class="lab" title="${r.lab}">${r.lab}</span></div>
      <div class="r"><span class="val">${r.val}</span>${r.trend==="up"?IC.trendUp(r.base,r.stroke):IC.trendDown(r.base,r.stroke)}</div>
    </div>`).join("");
}

/* ---- secondary: demographic bar ---- */
function renderBar(){
  const d=DATA[state.side], items=d.demo[state.dim]||[], overall=d.overall.default_rate;
  document.getElementById("barDesc").textContent=`${state.dim} · n=${fmtInt(items.reduce((a,b)=>a+b.clients,0))} clients`;
  document.getElementById("detDim").textContent=state.dim;
  const W=320,H=210,m={t:12,r:10,b:38,l:34}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const maxV=Math.max(overall,...items.map(i=>i.default_rate))*1.18;
  const s=newSvg(W,H);
  for(let k=0;k<=4;k++){const yv=maxV*k/4,y=m.t+ih-ih*(yv/maxV);
    s.appendChild(E("line",{class:"grid",x1:m.l,y1:y,x2:m.l+iw,y2:y}));
    s.appendChild(E("text",{class:"tick",x:m.l-5,y:y+3,"text-anchor":"end"},(yv*100).toFixed(0)+"%"));}
  const gap=iw/items.length, bw=gap*0.6, col=state.side==="etl"?"#EE4094":"#a78bfa";
  items.forEach((it,i)=>{const x=m.l+gap*i+(gap-bw)/2,bh=ih*(it.default_rate/maxV),y=m.t+ih-bh;
    s.appendChild(E("rect",{x,y,width:bw,height:bh,rx:3,fill:col,opacity:.9}));
    s.appendChild(E("text",{class:"tick",x:x+bw/2,y:y-4,"text-anchor":"middle",fill:"#e5e7eb"},(it.default_rate*100).toFixed(1)));
    s.appendChild(E("text",{class:"tick",x:x+bw/2,y:m.t+ih+14,"text-anchor":"middle"},it.category.length>8?it.category.slice(0,8)+"…":it.category));});
  const ry=m.t+ih-ih*(overall/maxV);
  s.appendChild(E("line",{class:"refline",x1:m.l,y1:ry,x2:m.l+iw,y2:ry}));
  const host=document.getElementById("barChart");host.innerHTML="";host.appendChild(s);
}

/* ---- secondary: scatter ---- */
function renderScatter(){
  const d=DATA[state.side], rows=d.monthly, key=state.macro;
  const ck={exchange_rate_twd_usd:"corr_fx",real_broad_eer:"corr_reer",total_reserves:"corr_reserves"}[key];
  document.getElementById("scatterDesc").textContent=`x=${MACRO_LABEL[key]} · y=default · r=${Number(d.corr[ck]).toFixed(3)}`;
  const W=320,H=210,m={t:12,r:12,b:34,l:38},iw=W-m.l-m.r,ih=H-m.t-m.b;
  const xs=rows.map(r=>r[key]),xMin=Math.min(...xs),xMax=Math.max(...xs),xp=(xMax-xMin||1)*.15;
  const ys=rows.map(r=>r.default_rate),yMid=ys.reduce((a,b)=>a+b,0)/ys.length,yLo=Math.min(...ys)-.05,yHi=Math.max(...ys)+.05;
  const X=v=>m.l+iw*((v-(xMin-xp))/((xMax+xp)-(xMin-xp))),Y=v=>m.t+ih-ih*((v-yLo)/(yHi-yLo));
  const s=newSvg(W,H);
  for(let k=0;k<=4;k++){const y=m.t+ih*k/4;s.appendChild(E("line",{class:"grid",x1:m.l,y1:y,x2:m.l+iw,y2:y}));
    s.appendChild(E("text",{class:"tick",x:m.l-5,y:y+3,"text-anchor":"end"},((yLo+(yHi-yLo)*(4-k)/4)*100).toFixed(0)+"%"));}
  s.appendChild(E("line",{class:"refline",x1:m.l,y1:Y(yMid),x2:m.l+iw,y2:Y(yMid)}));
  const col=state.side==="etl"?"#EE4094":"#a78bfa";
  rows.forEach(r=>{s.appendChild(E("circle",{cx:X(r[key]),cy:Y(r.default_rate),r:5.5,fill:col,opacity:.85}));
    s.appendChild(E("text",{class:"tick",x:X(r[key]),y:Y(r.default_rate)-8,"text-anchor":"middle"},r.month_name));});
  const host=document.getElementById("scatter");host.innerHTML="";host.appendChild(s);
}

function renderTable(){
  const d=DATA[state.side], items=d.demo[state.dim]||[], overall=d.overall.default_rate;
  let h='<table><tr><th>Category</th><th>Clients</th><th>Default rate</th><th>vs overall</th></tr>';
  items.forEach(it=>{const diff=it.default_rate-overall,c=diff>0?"#F08083":"#40E5D1";
    h+=`<tr><td>${it.category}</td><td class="mono">${fmtInt(it.clients)}</td><td class="mono">${pct(it.default_rate)}</td><td class="mono" style="color:${c}">${diff>=0?'+':''}${(diff*100).toFixed(2)} pp</td></tr>`;});
  document.getElementById("tableWrap").innerHTML=h+"</table>";
}

function renderInsight(){
  const d=DATA[state.side], cats=allCats(d);
  const hi=cats.slice().sort((a,b)=>b.default_rate-a.default_rate)[0];
  document.getElementById("insight").innerHTML=
    `<b>${state.side.toUpperCase()} warehouse.</b> Overall default rate <b>${pct(d.overall.default_rate)}</b> across <b>${fmtInt(d.overall.total_clients)}</b> clients. `+
    `Highest-risk group: <b>${hi.dim} = ${hi.category}</b> (${pct(hi.default_rate)}). `+
    `Default↔macro correlation ≈ <b>0</b> — the default label is a client-level constant copied across the six billing months, so it has no monthly variance to correlate with the macro series. `+
    `ETL and ELT produce identical KPIs, confirming both pipelines agree.`;
}

function renderAll(){renderLegend();renderArea();renderStats();renderMetrics();renderBar();renderScatter();renderTable();renderInsight();}

// controls
const dimSel=document.getElementById("dimSel");
Object.keys(DATA.etl.demo).forEach(dim=>{const o=document.createElement("option");o.value=dim;o.textContent=dim;dimSel.appendChild(o);});
state.dim = DATA.etl.demo.sex ? "sex" : Object.keys(DATA.etl.demo)[0];
dimSel.value=state.dim;
dimSel.onchange=e=>{state.dim=e.target.value;renderBar();renderTable();document.getElementById("detDim").textContent=state.dim;};
document.getElementById("macroSel").onchange=e=>{state.macro=e.target.value;renderScatter();};
document.getElementById("sideSel").onchange=e=>{state.side=e.target.value;renderAll();};
renderAll();
</script>
<style>@keyframes fade{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}</style>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
