"""Render the documentation Markdown files in docs/ to PDF.

Pipeline: Markdown -> styled HTML -> PDF.
* Primary renderer: Microsoft Edge headless (Chromium; built into Windows 11, no install).
* Fallback: xhtml2pdf (pure-Python) if Edge is not found.

Run (on the host)::

    python docs/build_pdfs.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent
TARGETS = ["DOKUMENTASI_LENGKAP", "PROSES_ETL_ELT", "CARA_MENJALANKAN", "HOSTING_ORACLE",
           "PANDUAN_BELAJAR_GITHUB_HOSTING", "PANDUAN_BELAJAR_TECH_STACK",
           "PANDUAN_LENGKAP_PEMBEDAHAN", "LAPORAN_UNIT_TESTING", "ERD_DATABASE",
           "DASHBOARD_PREVIEW", "PANDUAN_DASHBOARD_DETAIL", "PANDUAN_DASHBOARD_POWERBI"]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; line-height: 1.5;
       color: #1a1a1a; max-width: 100%; }
h1 { font-size: 20px; border-bottom: 2px solid #2b6cb0; padding-bottom: 4px; color: #1a3a5c; }
h2 { font-size: 15px; margin-top: 18px; border-bottom: 1px solid #cbd5e0; padding-bottom: 2px;
     color: #1a3a5c; page-break-after: avoid; }
h3 { font-size: 13px; color: #2b6cb0; page-break-after: avoid; }
code { font-family: Consolas, 'Courier New', monospace; background: #f0f3f7; padding: 1px 4px;
       border-radius: 3px; font-size: 10px; }
pre { background: #f3f4f6; color: #1f2937; border: 1px solid #d1d5db; padding: 10px 12px;
      border-radius: 6px; overflow-x: auto; font-size: 9.5px; line-height: 1.4;
      page-break-inside: avoid; white-space: pre-wrap; word-wrap: break-word; }
pre code { background: transparent; color: #1f2937; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 10px;
        page-break-inside: avoid; }
th, td { border: 1px solid #cbd5e0; padding: 4px 7px; text-align: left; vertical-align: top; }
th { background: #2b6cb0; color: #fff; }
tr:nth-child(even) td { background: #f6f8fb; }
blockquote { border-left: 4px solid #f6ad55; background: #fffaf0; margin: 8px 0; padding: 6px 12px;
             color: #4a3a1a; }
"""


def md_to_html(md_text: str, title: str) -> str:
    import markdown  # ensured installed by main()

    body = markdown.markdown(
        md_text, extensions=["fenced_code", "tables", "toc", "sane_lists", "nl2br"]
    )
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>"
    )


def find_edge() -> str | None:
    for p in (
        rf"{os.environ.get('ProgramFiles(x86)', '')}\Microsoft\Edge\Application\msedge.exe",
        rf"{os.environ.get('ProgramFiles', '')}\Microsoft\Edge\Application\msedge.exe",
    ):
        if p and Path(p).exists():
            return p
    return shutil.which("msedge")


def render_edge(edge: str, html_path: Path, pdf_path: Path) -> bool:
    uri = html_path.resolve().as_uri()
    # A unique, isolated user-data-dir per invocation avoids Edge's shared-profile
    # lock: back-to-back headless runs otherwise collide and emit near-blank PDFs.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="edge-pdf-") as profile:
        cmd = [edge, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
               f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
               # let the page fully load/layout before printing — without this, Edge
               # headless often prints a blank/truncated page for local file:// URIs.
               "--virtual-time-budget=10000", "--run-all-compositor-stages-before-draw",
               f"--print-to-pdf={pdf_path}", uri]
        subprocess.run(cmd, check=True, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Guard against Edge's silent blank-PDF failure: a real render of these docs is
    # comfortably >8 KB. Treat anything smaller as a failure so the caller can fall
    # back to xhtml2pdf.
    return pdf_path.exists() and pdf_path.stat().st_size > 8192


def _link_callback(uri: str, rel: str) -> str:
    """Resolve relative image/CSS URIs (e.g. ``../warehouse/x.png``) to abs paths
    so embedded images render. Tries the docs/ dir then the repo root."""
    for base in (DOCS, DOCS.parent):
        p = (base / uri).resolve()
        if p.exists():
            return str(p)
    return uri


def render_xhtml2pdf(html: str, pdf_path: Path) -> bool:
    from xhtml2pdf import pisa  # type: ignore

    with pdf_path.open("wb") as fh:
        status = pisa.CreatePDF(html, dest=fh, link_callback=_link_callback)
    return not status.err and pdf_path.stat().st_size > 0


def ensure(pkg: str) -> None:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", pkg], check=True)


def main() -> int:
    ensure("markdown")
    # xhtml2pdf (pure-Python) is the reliable default — Edge headless was observed
    # silently emitting blank/empty PDFs on some Windows builds. Opt into Edge (for
    # higher CSS fidelity) with USE_EDGE=1 when it's known good on the machine.
    edge = find_edge() if os.environ.get("USE_EDGE") == "1" else None
    print(f"Renderer: {'Edge headless (USE_EDGE=1)' if edge else 'xhtml2pdf'}")
    if not edge:
        ensure("xhtml2pdf")

    ok = 0
    for name in TARGETS:
        md_path = DOCS / f"{name}.md"
        if not md_path.exists():
            print(f"  skip {name}: no .md")
            continue
        html = md_to_html(md_path.read_text(encoding="utf-8"), name)
        html_path = DOCS / f"{name}.html"
        html_path.write_text(html, encoding="utf-8")
        pdf_path = DOCS / f"{name}.pdf"
        try:
            done = render_edge(edge, html_path, pdf_path) if edge else render_xhtml2pdf(html, pdf_path)
        except Exception as exc:  # noqa: BLE001 — try fallback on any Edge failure
            print(f"  {name}: primary renderer failed ({exc}); trying xhtml2pdf")
            ensure("xhtml2pdf")
            done = render_xhtml2pdf(html, pdf_path)
        if done:
            ok += 1
            print(f"  OK  {pdf_path.name}  ({pdf_path.stat().st_size // 1024} KB)")
        else:
            print(f"  FAIL {name}")
        html_path.unlink(missing_ok=True)
    print(f"Done: {ok}/{len(TARGETS)} PDFs generated in {DOCS}")
    return 0 if ok == len(TARGETS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
