"""Build prompts + offline fallback blog (no hallucination)."""
from __future__ import annotations

import re

from ingest.resolver import ProjectContext
from generator.templates import SYSTEM_PROMPT, BLOG_USER_TEMPLATE, FALLBACK_BLOG


def build_system(author: str, repo: str) -> str:
    return SYSTEM_PROMPT.format(author=author or "the author", repo=repo or "the repo")


def build_user(ctx: ProjectContext, author: str) -> str:
    return BLOG_USER_TEMPLATE.format(
        evidence=ctx.evidence_pack(), author=author or "the author",
        repo=ctx.repo_url or "(no public repo)",
    )


def fallback_blog(ctx: ProjectContext, author: str) -> tuple[str, dict]:
    """Rule-based draft used for --dry-run and when no LLM key is set.
    Only rephrases evidence; adds zero new claims."""
    problem = (ctx.description_raw or ctx.readme.split("\n")[0] if ctx.readme else "A personal project I worked on.").strip()[:400]
    if ctx.source_type == "text":
        built = ctx.description_raw[:800]
    elif ctx.readme:
        built = f"Per the repo README: {ctx.readme[:600].strip()}"
    else:
        built = f"Source: {ctx.source_ref}. File layout includes: {ctx.file_tree[:400] or 'see repo'}."
    stack = "\n".join(f"- {s}" for s in ctx.tech_stack) if ctx.tech_stack else "- (stack not auto-detected — edit before publishing)"
    commits = ctx.commits[0] if ctx.commits else ""
    decision = (f"Recent work: `{commits}`. " if commits else "") + "Tradeoffs and alternatives: [FILL IN — 2 sentences about one decision you made and why.]"
    nxt = "[FILL IN — one thing that broke or is still TODO. Honest > impressive.]"
    repo_line = f" Repo: {ctx.repo_url}" if ctx.repo_url else ""
    md = FALLBACK_BLOG.format(title=ctx.title, problem=problem, built=built.strip(),
                              stack=stack, decision=decision, next=nxt,
                              author=author or "me", repo_line=repo_line)
    meta = {"title": ctx.title[:60], "tags": ["showdev"],
            "tldr": (ctx.description_raw or ctx.title)[:140],
            "linkedin": f"Shipped {ctx.title} — notes on what I built and what broke."}
    return md, meta


def split_llm_output(text: str) -> tuple[str, dict]:
    """Split 'markdown %%% yaml-ish' output from the LLM."""
    if "%%%" not in text:
        return text.strip(), {}
    md, tail = text.split("%%%", 1)
    meta: dict = {}
    for line in tail.strip().splitlines():
        m = re.match(r"^(title|tldr|linkedin)\s*:\s*(.+)$", line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
        m2 = re.match(r"^tags\s*:\s*\[(.*)\]$", line.strip())
        if m2:
            meta["tags"] = [t.strip().strip("'\"").lower() for t in m2.group(1).split(",") if t.strip()]
    return md.strip(), meta
