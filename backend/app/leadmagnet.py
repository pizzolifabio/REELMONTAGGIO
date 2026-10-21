"""Impaginazione del lead magnet (HTML in stile Apple) ed esportazione PDF con Chrome headless."""
import html
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .config import settings

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", sans-serif;
  color: #1d1d1f; background: #fff; -webkit-font-smoothing: antialiased; }
.page { max-width: 760px; margin: 0 auto; padding: 72px 56px; }
.eyebrow { font-size: 13px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #0071e3; }
h1 { font-family: -apple-system, "SF Pro Display", "Helvetica Neue", sans-serif; font-size: 44px; line-height: 1.08;
  letter-spacing: -0.02em; margin: 12px 0 12px; font-weight: 700; }
.subtitle { font-size: 21px; line-height: 1.4; color: #6e6e73; margin: 0 0 36px; }
.intro { font-size: 17px; line-height: 1.6; padding: 24px 28px; background: #f5f5f7; border-radius: 18px; margin-bottom: 40px; }
section { break-inside: avoid; margin-bottom: 32px; }
h2 { font-size: 24px; letter-spacing: -0.01em; margin: 0 0 10px; display: flex; gap: 12px; align-items: baseline; }
h2 .n { color: #0071e3; font-variant-numeric: tabular-nums; }
p { font-size: 16px; line-height: 1.6; margin: 0 0 12px; }
ul { list-style: none; padding: 0; margin: 0; }
li { font-size: 16px; line-height: 1.5; padding: 10px 0 10px 32px; position: relative; border-top: 1px solid #e8e8ed; }
li::before { content: ""; position: absolute; left: 4px; top: 15px; width: 14px; height: 14px; border-radius: 4px;
  border: 1.5px solid #0071e3; }
.closing { margin-top: 48px; padding-top: 28px; border-top: 1px solid #d2d2d7; font-size: 17px; line-height: 1.6; color: #424245; }
.actions { margin: 0 0 40px; }
.btn { display: inline-block; background: #0071e3; color: #fff; text-decoration: none; padding: 12px 22px;
  border-radius: 980px; font-size: 15px; font-weight: 500; }
@media print { .actions { display: none; } .page { padding: 56px 56px; } }
@media (prefers-color-scheme: dark) { @media screen {
  body { background: #000; color: #f5f5f7; } .intro { background: #1c1c1e; } li { border-color: #2c2c2e; }
  .subtitle, .closing { color: #a1a1a6; } .closing { border-color: #38383a; } } }
@media (max-width: 600px) { .page { padding: 40px 20px; } h1 { font-size: 32px; } }
"""


def render_html(lead: dict[str, Any], pdf_url: str | None = None) -> str:
    e = html.escape
    sections = []
    for i, sec in enumerate(lead.get("sections", []), 1):
        body = "".join(f"<p>{e(p)}</p>" for p in str(sec.get("body", "")).split("\n") if p.strip())
        items = "".join(f"<li>{e(it)}</li>" for it in sec.get("items", []))
        sections.append(
            f"<section><h2><span class='n'>{i:02d}</span>{e(sec.get('heading', ''))}</h2>{body}"
            f"{'<ul>' + items + '</ul>' if items else ''}</section>"
        )
    actions = f"<div class='actions'><a class='btn' href='{e(pdf_url)}'>Scarica PDF</a></div>" if pdf_url else ""
    return f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(lead.get('title', 'Guida'))}</title>
<style>{CSS}</style></head><body><main class="page">
<div class="eyebrow">{e(lead.get('type', 'Guida'))}</div>
<h1>{e(lead.get('title', ''))}</h1>
<p class="subtitle">{e(lead.get('subtitle', ''))}</p>
{actions}
<div class="intro">{e(lead.get('intro', ''))}</div>
{''.join(sections)}
<div class="closing">{e(lead.get('closing', ''))}</div>
</main></body></html>"""


def export_pdf(lead: dict[str, Any], output: Path) -> Path:
    chrome = settings.chrome_bin
    if not Path(chrome).exists():
        raise RuntimeError("Google Chrome non trovato: imposta CHROME_BIN in .env per generare i PDF")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "lead.html"
        src.write_text(render_html(lead), encoding="utf-8")
        subprocess.run(
            [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={tmp}/profile", f"--print-to-pdf={output}", src.as_uri()],
            capture_output=True, timeout=120, check=True,
        )
    if not output.exists():
        raise RuntimeError("Chrome non ha prodotto il PDF")
    return output
