#!/usr/bin/env python3
"""worklog — authentic work-only publisher.

Usage:
  python cli.py publish --source ../sidekick --dry-run
  python cli.py publish --source https://github.com/owner/repo --targets devto,hashnode --llm openai
  python cli.py publish --source "Built an offline-first geotag camera..." --llm opencode
  python cli.py publish --source ../sidekick --from-file output/sidekick-20240101-blog.md

Flow:
  1. resolve source -> ProjectContext (evidence only, no invention)
  2. generate blog: --llm opencode (default, manual paste) | openai | anthropic | ollama
  3. write output/<slug>-blog.md + <slug>-linkedin.txt (+ medium export)
  4. publish to --targets unless --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingest.resolver import resolve
from generator.builder import build_system, build_user, fallback_blog, split_llm_output
from llm.providers import generate, LLMError
from publisher import devto, hashnode, medium_export, linkedin
from publisher.state import record


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return (s or "project")[:50]


def load_env() -> None:
    for name in (".env", "../.env"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        if os.path.isfile(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    load_env()
    ap = argparse.ArgumentParser(prog="worklog")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish", help="turn work into blog + linkedin + publishes")
    p.add_argument("--source", required=True, help="local path | github url | free-text description")
    p.add_argument("--targets", default="devto,hashnode,medium,linkedin",
                   help="comma list: devto,hashnode,medium,linkedin")
    p.add_argument("--llm", default="opencode", choices=["opencode", "openai", "anthropic", "ollama"])
    p.add_argument("--dry-run", action="store_true", help="generate files only, no network posts")
    p.add_argument("--from-file", default="", help="skip generation, use existing blog markdown file")
    p.add_argument("--draft", action="store_true", default=True, help="publish as draft (default true)")
    p.add_argument("--live", action="store_true", help="publish publicly instead of draft")
    sub.add_parser("hashnode-auth", help="connect Hashnode via OAuth (browser approval)")
    sub.add_parser("hashnode-tools", help="list tools on Hashnode's MCP server")
    args = ap.parse_args()

    if args.cmd == "hashnode-auth":
        from publisher.hashnode_auth import run as auth_run
        print(auth_run())
        return
    if args.cmd == "hashnode-tools":
        from publisher import hashnode as hn
        print(json.dumps(hn.list_tools(), indent=2))
        return

    author = os.environ.get("AUTHOR_NAME", "")
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(out_dir, exist_ok=True)

    ctx = resolve(args.source)
    slug = f"{slugify(ctx.title)}-{datetime.date.today().strftime('%Y%m%d')}"
    draft = not args.live

    # --- 1. blog markdown ---
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            blog_md = f.read()
        h1 = re.search(r"^#\s+(.+)$", blog_md, re.M)
        meta: dict = {"title": (h1.group(1).strip() if h1 else ctx.title)[:90],
                       "tags": ["showdev", "webdev", "react", "javascript"]}
    elif args.llm == "opencode":
        # Manual opencode-native path: evidence pack + prompt, fallback draft now
        blog_md, meta = fallback_blog(ctx, author)
        prompt_path = os.path.join(out_dir, f"{slug}-PROMPT.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write("# Paste this into opencode (any free model, e.g. Muse Spark)\n\n"
                    f"## SYSTEM\n{build_system(author, ctx.repo_url)}\n\n## USER\n{build_user(ctx, author)}\n")
        print(f"[opencode] No API key needed. Prompt written to:\n  {prompt_path}")
        print("  Paste it into opencode, copy the markdown back, then re-run with --from-file <pasted.md>")
    else:
        try:
            raw = generate(args.llm, build_system(author, ctx.repo_url), build_user(ctx, author))
            blog_md, meta = split_llm_output(raw)
            if not blog_md:
                raise LLMError("empty LLM output")
        except LLMError as e:
            print(f"[llm:{args.llm}] failed ({e}) — using offline fallback draft.", file=sys.stderr)
            blog_md, meta = fallback_blog(ctx, author)

    title = meta.get("title", ctx.title)[:90]
    tags = meta.get("tags", ["showdev"])[:4]
    # strip a duplicate top-level title if the model echoed it
    blog_path = os.path.join(out_dir, f"{slug}-blog.md")
    with open(blog_path, "w", encoding="utf-8") as f:
        f.write(blog_md if blog_md.startswith("#") else f"# {title}\n\n{blog_md}")
    print(f"[draft] {blog_path}")

    # --- 2. linkedin draft (always local file, never auto-post) ---
    targets = [t.strip().lower() for t in args.targets.split(",")]
    bullets = [ctx.description_raw[:120] or title,
               f"Stack: {', '.join(ctx.tech_stack[:3]) or 'see write-up'}",
               (ctx.commits[0] if ctx.commits else "Notes + repo link inside")]
    li = linkedin.build_draft(meta.get("linkedin", f"Shipped {title} — short notes on what worked and what broke."),
                              bullets, "<paste blog URL after publishing>", tags, out_dir, slug)
    print(f"[linkedin draft] {li['path']} ({li['chars']} chars) — copy-paste to LinkedIn.")

    if "medium" in targets:
        m = medium_export.export(title, blog_md, out_dir, slug)
        print(f"[medium] {m['path']}\n  {m['instructions']}")

    # --- 3. network publishes ---
    results: dict = {"slug": slug, "title": title, "targets": targets, "results": {}}
    if args.dry_run:
        print("[dry-run] skipping network. Review files, then re-run without --dry-run.")
        record(out_dir, results)
        return

    canonical = os.environ.get("CANONICAL_BASE_URL", "")
    if "devto" in targets:
        r = devto.publish(title, blog_md, tags, canonical, draft=draft)
        results["results"]["devto"] = r
        print(f"[dev.to] {r}")
        if r.get("url") and not canonical:
            canonical = r["url"]  # reuse as canonical/linkedin link
    if "hashnode" in targets:
        r = hashnode.publish(title, blog_md, tags, draft=draft, canonical=canonical)
        results["results"]["hashnode"] = r
        print(f"[hashnode] {r}")
    record(out_dir, results)
    first_url = next((v.get("url") for v in results["results"].values() if isinstance(v, dict) and v.get("url")), "")
    if first_url:
        print(f"\nDone. Update your LinkedIn draft's URL line with:\n  {first_url}")


if __name__ == "__main__":
    main()
