"""Build prompts + offline fallback content (no hallucination).

LLM output format:  BLOG %%% LINKEDIN %%% X %%% META(yaml-ish)
Returns (blog_md, linkedin_post, x_thread, meta).
"""
from __future__ import annotations

import re

from ingest.resolver import ProjectContext
from generator.templates import (
    SYSTEM_PROMPT, BLOG_USER_TEMPLATE, FALLBACK_BLOG,
    FALLBACK_LINKEDIN, FALLBACK_X,
)


def build_system(author: str, repo: str) -> str:
    return SYSTEM_PROMPT  # no placeholders left; author/repo go in user msg


def build_user(ctx: ProjectContext, author: str, media: str = "") -> str:
    return BLOG_USER_TEMPLATE.format(
        evidence=ctx.evidence_pack(), author=author or "the author",
        repo=ctx.repo_url or "(no public repo)",
        media=media or "(no screenshots yet — suggest placements only)",
    )


def _core_facts(ctx: ProjectContext) -> dict:
    problem = (ctx.description_raw or ctx.readme.split("\n")[0] if ctx.readme else
               "A personal project I worked on.").strip()[:400]
    if ctx.source_type == "text":
        built = ctx.description_raw[:800]
    elif ctx.readme:
        built = f"Per the repo README: {ctx.readme[:600].strip()}"
    else:
        built = f"Source: {ctx.source_ref}. File layout includes: {ctx.file_tree[:400] or 'see repo'}."
    stack = "\n".join(f"- {s}" for s in ctx.tech_stack) if ctx.tech_stack else \
        "- (stack not auto-detected — edit before publishing)"
    commits = ctx.commits[0] if ctx.commits else ""
    return {"problem": problem, "built": built.strip(), "stack": stack, "commit": commits}


def fallback_blog(ctx: ProjectContext, author: str) -> tuple[str, dict]:
    """Rule-based draft used for --dry-run and when no LLM key is set.
    Only rephrases evidence; adds zero new claims."""
    f = _core_facts(ctx)
    decision = ((f"Recent work: `{f['commit']}`. " if f["commit"] else "") +
                "Tradeoffs and alternatives: [FILL IN — 2 sentences about one decision you made and why.]")
    nxt = "[FILL IN — one thing that broke or is still TODO. Honest > impressive.]"
    repo_line = f" Repo: {ctx.repo_url}" if ctx.repo_url else ""
    md = FALLBACK_BLOG.format(title=ctx.title, problem=f["problem"], built=f["built"],
                              stack=f["stack"], decision=decision, next=nxt,
                              author=author or "me", repo_line=repo_line)
    meta = {"title": ctx.title[:60], "tags": ["showdev"],
            "tldr": (ctx.description_raw or ctx.title)[:140]}
    return md, meta


def fallback_linkedin(ctx: ProjectContext, author: str) -> str:
    from generator.templates import FALLBACK_LINKEDIN as T
    f = _core_facts(ctx)
    stack1 = ctx.tech_stack[0] if ctx.tech_stack else "the stack in the repo"
    return T.format(
        hook=f"Spent my recent dev time on {ctx.title} — {f['problem'][:120]}",
        b1=f["built"][:350],
        b2=f"Built with {stack1}." +
           (f" Most recent commit: {f['commit']}." if f["commit"] else "") +
           " [FILL IN — one concrete detail: a number, a tradeoff, a surprise.]",
        lesson="[FILL IN — one thing you'd do differently.]",
        repo=ctx.repo_url or "[repo link]",
        url="<paste blog URL after publishing>",
        tags="#BuildInPublic #SoftwareEngineering",
    )


def fallback_x(ctx: ProjectContext) -> str:
    from generator.templates import FALLBACK_X as T
    f = _core_facts(ctx)
    stack = ", ".join(ctx.tech_stack[:3]) or "see repo"
    return T.format(
        t1=f"1/ I built {ctx.title}: {(ctx.description_raw or ctx.title)[:180]}",
        t2=f"2/ Stack: {stack}. {f['problem'][:150]}",
        t3=f"3/ [FILL IN — one technical detail worth sharing.]",
        t4="4/ [FILL IN — what broke or what's next.]",
        repo=ctx.repo_url or "[repo link]",
        url="<paste blog URL after publishing>",
        tags="#buildinpublic",
    )


def split_llm_output(text: str) -> tuple[str, str, str, dict]:
    """Split 'BLOG %%% LINKEDIN %%% X %%% META' output from the LLM."""
    if "%%%" not in text:
        return text.strip(), "", "", {}
    parts = [p.strip() for p in text.split("%%%")]
    blog = parts[0] if len(parts) > 0 else ""
    linkedin = parts[1] if len(parts) > 1 else ""
    if len(parts) > 3:
        x, tail = parts[2], parts[3]
    elif len(parts) == 3:
        # ambiguous: could be old-format (blog %%% meta) or (blog %%% linkedin %%% x)
        x, tail = "", ""
        if re.search(r"^(title|tags|tldr)\s*:", parts[2], re.M):
            tail = parts[2]
            linkedin = ""
        else:
            x = parts[2]
    else:
        x, tail = "", parts[1] if re.search(r"^(title|tags|tldr)\s*:", parts[1], re.M) else ""
        if not tail:
            linkedin = parts[1]
    meta: dict = {}
    for line in tail.strip().splitlines():
        m = re.match(r"^(title|tldr)\s*:\s*(.+)$", line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
        m2 = re.match(r"^tags\s*:\s*\[(.*)\]$", line.strip())
        if m2:
            meta["tags"] = [t.strip().strip("'\"").lower() for t in m2.group(1).split(",") if t.strip()]
    return blog, linkedin, x, meta
