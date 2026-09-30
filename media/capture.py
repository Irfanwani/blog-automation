"""Python wrapper: capture screenshots + demo video, wire images into the blog.

Image hosting reality: blog APIs need PUBLIC image URLs. The zero-cost host
you control is your own repo: screenshots are copied to <project>/docs/demo/
and referenced as raw.githubusercontent.com URLs. Files stay untracked until
you commit+push — CLI warns if they aren't pushed yet.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

CAPTURE_MJS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capture.mjs")


def capture(url: str, out_dir: str, slug: str) -> dict:
    r = subprocess.run(["node", CAPTURE_MJS, url, out_dir, slug],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"capture failed:\n{(r.stderr or r.stdout)[-1500:]}")
    for line in r.stdout.strip().splitlines()[::-1]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise RuntimeError(f"capture produced no manifest:\n{r.stdout[-500:]}")


def repo_raw_base(repo_url: str, branch: str = "main") -> str:
    m = re.search(r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url or "")
    if not m:
        return ""
    return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{branch}/docs/demo/"


def publish_images(manifest: dict, project_dir: str, repo_url: str, out_dir: str) -> tuple[list[str], str]:
    """Copy shots to <project>/docs/demo, return (local_paths, raw_base_url_or_empty)."""
    demo_dir = os.path.join(project_dir, "docs", "demo")
    os.makedirs(demo_dir, exist_ok=True)
    for src in manifest.get("shots", []):
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(demo_dir, os.path.basename(src)))
    branch = "main"
    try:
        b = subprocess.run(["git", "-C", project_dir, "branch", "--show-current"],
                           capture_output=True, text=True, timeout=10).stdout.strip()
        if b:
            branch = b
    except (OSError, subprocess.SubprocessError):
        pass
    return manifest.get("shots", []), repo_raw_base(repo_url, branch)


def embed_images(blog_md: str, shots: list[str], raw_base: str) -> str:
    """Replace <!-- SCREENSHOT: desc --> comments with real image markdown.
    Falls back to appending a screenshots section if there are no placeholders."""
    descs = re.findall(r"<!--\s*SCREENSHOT:\s*(.+?)\s*-->", blog_md)
    urls = [(raw_base + os.path.basename(s)) if raw_base else os.path.basename(s) for s in shots]
    if descs and urls:
        it = iter(urls)
        def repl(m):
            try:
                u = next(it)
            except StopIteration:
                u = urls[-1]
            return f"![{m.group(1).strip()}]({u})"
        blog_md = re.sub(r"<!--\s*SCREENSHOT:\s*(.+?)\s*-->", repl, blog_md)
    elif urls:
        blog_md += "\n\n## Screenshots\n" + "\n".join(f"![demo]({u})" for u in urls) + "\n"
    return blog_md
