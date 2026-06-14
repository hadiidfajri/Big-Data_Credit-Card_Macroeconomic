"""Render ``report/report.md`` to PDF and place ``report.pdf`` at the repo root.

Uses the same pure-Python pipeline as ``docs/build_pdfs.py`` (Markdown -> styled
HTML -> PDF via xhtml2pdf), plus a ``link_callback`` so the embedded images
(``architecture_diagram.png``, ``warehouse/erd_star_schema.png``) resolve from the
repo root regardless of the working directory.

Run::

    python report/build_report_pdf.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent
REPO_ROOT = REPORT_DIR.parent


def ensure(pkg: str) -> None:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", pkg], check=True)


def link_callback(uri: str, rel: str) -> str:
    """Resolve image/CSS URIs (relative to report/ then repo root) to abs paths."""
    for base in (REPORT_DIR, REPO_ROOT):
        p = (base / uri).resolve()
        if p.exists():
            return str(p)
    return uri


def main() -> int:
    ensure("markdown")
    ensure("xhtml2pdf")
    import markdown  # noqa: E402
    from xhtml2pdf import pisa  # noqa: E402

    # Inline a compact stylesheet (kept independent of docs/build_pdfs import).
    style = """
    @page { size: A4; margin: 16mm 14mm; }
    body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; line-height: 1.5; color: #1a1a1a; }
    h1 { font-size: 20px; border-bottom: 2px solid #2b6cb0; padding-bottom: 4px; color: #1a3a5c; }
    h2 { font-size: 15px; margin-top: 16px; border-bottom: 1px solid #cbd5e0; color: #1a3a5c; }
    h3 { font-size: 13px; color: #2b6cb0; }
    code { font-family: Consolas, monospace; background: #f0f3f7; padding: 1px 4px; font-size: 10px; }
    pre { background: #f3f4f6; color: #1f2937; border: 1px solid #d1d5db; padding: 10px; font-size: 9.5px; }
    pre code { background: transparent; color: #1f2937; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 10px; }
    th, td { border: 1px solid #cbd5e0; padding: 4px 7px; text-align: left; }
    th { background: #2b6cb0; color: #fff; }
    img { max-width: 100%; }
    blockquote { border-left: 4px solid #f6ad55; background: #fffaf0; padding: 6px 12px; color: #4a3a1a; }
    """
    body = markdown.markdown(
        (REPORT_DIR / "report.md").read_text(encoding="utf-8"),
        extensions=["fenced_code", "tables", "sane_lists"],
    )
    html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>{style}</style></head><body>{body}</body></html>")

    out_report = REPORT_DIR / "report.pdf"
    with out_report.open("wb") as fh:
        status = pisa.CreatePDF(html, dest=fh, link_callback=link_callback)
    if status.err or out_report.stat().st_size == 0:
        print("FAILED to render report.pdf")
        return 1

    root_copy = REPO_ROOT / "report.pdf"
    shutil.copyfile(out_report, root_copy)
    print(f"OK  {out_report}  ({out_report.stat().st_size // 1024} KB)")
    print(f"OK  {root_copy}  (copied to repo root)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
