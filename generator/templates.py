"""Authentic work-only voice. Anti-fluff by design. Platform-native variants."""

SYSTEM_PROMPT = """You are a senior content engineer writing for a working developer.
BLOGGING CONTRACT (non-negotiable):
1. Write ONLY about what is in the PROJECT EVIDENCE. Never invent features, metrics, users, or benchmarks.
2. No hype, no growth-hack tone, no "revolutionary/game-changer/unlock". Plain, specific, honest.
3. If evidence is thin, say what is unknown and what you actually built. Shorter is better than padded.
4. First person. Code snippet only if evidence supports it (max 1, under 25 lines).
"""

BLOG_TASK = """Write a 500-800 word dev blog post for DEV.TO/HASHNODE/MEDIUM (developer audience).
Structure: real problem -> what you built -> one technical decision with tradeoff -> what broke / what you'd do differently -> repo link + how to run.
Output valid Markdown starting with '# ' title, then sections. End with '---\\nBuilt by {author}. Repo: {repo}'.
Leave image placeholders where a screenshot would help, as HTML comments: <!-- SCREENSHOT: what to show -->.
"""

LINKEDIN_TASK = """Write a LINKEDIN post (NOT a blog pointer — a standalone post, 120-200 words).
Voice: professional peer talking to peers. Open with a specific moment or frustration (no "thrilled to announce", no "excited to share").
Body: what you built, one concrete detail or number from the evidence, one honest lesson or open problem.
Close with exactly one line: the repo link and/or 'Full write-up: <URL>'.
Max 4 hashtags, inline-relevant (#SystemDesign #React #BuildInPublic style).
Short paragraphs, line breaks between them. No emoji spam (max 2, or zero).
"""

X_TASK = """Write an X/TWITTER thread (NOT a link drop — native to the platform).
Tweet 1 (the hook, <=280 chars): surprising or concrete claim from the evidence, no hashtags, no link.
Tweets 2-5 (each <=280 chars): one idea each — what it does, one technical detail, what broke, what's next.
Final tweet: repo link + full write-up <URL> + max 2 hashtags.
Number them 1/ 2/ ... Keep each tweet self-contained (threads get unrolled and quoted).
"""

BLOG_USER_TEMPLATE = """PROJECT EVIDENCE:
{evidence}

AUTHOR: {author}
REPO LINK TO USE (or omit if none): {repo}
SCREENSHOTS TAKEN (reference them, don't invent others): {media}

Do these three tasks in order, separated by a line containing only '%%%' between each:

--- TASK 1: BLOG ---
""" + BLOG_TASK + """
--- TASK 2: LINKEDIN ---
""" + LINKEDIN_TASK + """
--- TASK 3: X ---
""" + X_TASK + """
After the last task, output AFTER another '%%%' line a YAML block:
title: <60 chars>
tags: [up to 4, lowercase, from: javascript, typescript, python, react, reactnative, expo, nextjs, flutter, ios, android, webdev, ai, tutorial, showdev]
tldr: <one sentence, 140 chars>
"""

LINKEDIN_TEMPLATE = """{hook}

What I actually did:
- {b1}
- {b2}
- {b3}

Full write-up: {url}

#buildinpublic #softwareengineering {tags}
"""

FALLBACK_LINKEDIN = """{hook}

Here's what that actually involved:

{b1}

{b2}

The part I'd do differently: {lesson}

Repo: {repo}
Full write-up: {url}

{tags}"""

FALLBACK_X = """{t1}

{t2}

{t3}

{t4}

Repo: {repo}
Full write-up: {url} {tags}"""

FALLBACK_BLOG = """# {title}: what I actually built

> Work note, not a tutorial — this documents what exists in the repo today.

## The problem
{problem}

## What I built
{built}

## Stack (from the repo, not from memory)
{stack}

## One technical decision
{decision}

## What broke / what's next
{next}

---
Built by {author}.{repo_line}
"""
