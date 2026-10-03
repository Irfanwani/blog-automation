"""Series-styled cover images (1000x420, dev.to size) via Playwright.

Usage: make_cover(out_dir, slug, kicker, title, sub, side) -> png path.
HTML lives in memory; render at 2x for crispness. No AI image gen, no mockups —
typographic covers in the project's terminal aesthetic.
"""
from __future__ import annotations

import html
import os
import re
import subprocess

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1000px;height:420px;background:#0a0f0d;color:#e8f0ec;
font-family:'JetBrains Mono',monospace;display:flex;overflow:hidden}}
.bar{{width:14px;background:linear-gradient(#3ddc84,#1a9e5c)}}
.main{{flex:1;padding:48px 52px;display:flex;flex-direction:column;justify-content:center}}
.kicker{{color:#3ddc84;font-size:25px;letter-spacing:3px;margin-bottom:16px}}
h1{{font-size:{tsize}px;line-height:1.14;font-weight:700}}
h1 .dim{{color:#8fa89b}}
.sub{{margin-top:20px;font-size:24px;color:#8fa89b}}
.sub b{{color:#e8f0ec}}.prompt{{color:#3ddc84}}
.side{{width:290px;background:#0d1512;border-left:1px solid #1e2b25;
padding:36px 28px;font-size:20px;line-height:2.05;color:#8fa89b}}
.ok{{color:#3ddc84}}.no{{color:#ff6b6b}}
</style></head><body><div class="bar"></div><div class="main">
<div class="kicker">{kicker}</div><h1>{title}</h1><div class="sub">{sub}</div>
</div><div class="side">{side}</div></body></html>"""

SHOT_MJS = """import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 420 }, deviceScaleFactor: 2 });
await page.goto(process.argv[2], { waitUntil: 'networkidle', timeout: 30000 });
await page.screenshot({ path: process.argv[3] });
await browser.close();
"""


def _wrap(title: str, per_line: int = 22) -> str:
    words, lines, cur = title.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > per_line and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "<br>".join(html.escape(l) for l in lines[:3])


def derive_fields(meta_title: str, tldr: str, tags: list[str], project: str) -> tuple:
    m = re.search(r"(.+?)\s+[Pp]art\s+(\d+)\s*[:\-–]?\s*(.*)$", meta_title)
    if m:
        kicker = f"{m.group(1).strip().upper()} · PART {m.group(2)}"
        title = m.group(3).strip() or meta_title
    else:
        kicker = (project or "WORK NOTE").upper()[:28]
        title = meta_title
    size = 60 if len(title) <= 30 else (52 if len(title) <= 48 else 44)
    clipped = tldr[:80]
    if len(tldr) > 80:
        clipped = clipped.rsplit(" ", 1)[0] + "…"
    sub = f'<span class="prompt">›</span> {html.escape(clipped)}' if tldr else ""
    side_lines = "".join(f'<div><span class="ok">✓</span> #{html.escape(t)}</div>' for t in (tags or [])[:3])
    side_lines += '<div style="margin-top:12px"><span class="ok">✓</span> zero fluff</div>'
    return kicker, _wrap(title), sub, side_lines, size


def make_cover(out_dir: str, slug: str, meta_title: str, tldr: str = "",
               tags: list[str] | None = None, project: str = "") -> str:
    kicker, title, sub, side, size = derive_fields(meta_title, tldr, tags or [], project)
    page = TEMPLATE.format(kicker=html.escape(kicker), title=title, sub=sub,
                           side=side, tsize=size)
    html_path = os.path.join(out_dir, f"{slug}-cover.html")
    png_path = os.path.join(out_dir, f"{slug}-cover.png")
    mjs_path = os.path.join(out_dir, "_cover-shot.mjs")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(page)
    with open(mjs_path, "w", encoding="utf-8") as f:
        f.write(SHOT_MJS)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)  # work-presence/ (node_modules lives here)
    r = subprocess.run(["node", mjs_path, "file://" + html_path, png_path],
                       capture_output=True, text=True, timeout=120, cwd=root)
    try:
        os.unlink(mjs_path)
    except OSError:
        pass
    if r.returncode != 0:
        raise RuntimeError(f"cover render failed:\n{(r.stderr or r.stdout)[-800:]}")
    return png_path
