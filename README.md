# work-presence — work-only tech presence, no fake content

Prompt with a **local path, GitHub URL, or description** → get an evidence-backed blog → publish to **dev.to + Hashnode** (API), **Medium** (1-click import), a full **LinkedIn post** + **X thread** (copy-paste drafts), with **screenshots in blogs and a demo video for LinkedIn/X** captured from your running project.

## Quickstart

```bash
cd work-presence
cp .env.example .env   # fill DEVTO_API_KEY; then: python cli.py hashnode-auth

# 1. Dry run — works with ZERO keys, uses opencode-native flow
python cli.py publish --source ../sidekick --dry-run
python cli.py publish --source https://github.com/owner/repo --dry-run
python cli.py publish --source "Built offline-first geotag camera with ..." --dry-run

# 2. Write the real post in opencode (any free model, e.g. Muse Spark):
#    open output/<slug>-PROMPT.md, paste into chat, save answer to output/<slug>-final.md

# 3. Publish (asks nothing, posts as drafts by default)
python cli.py publish --source ../sidekick --from-file output/<slug>-final.md
python cli.py publish --source ../sidekick --from-file output/<slug>-final.md --live  # public, not draft

# With demo media (local web projects): starts the dev server, captures
# 3 screenshots + a 10-30s demo video, embeds shots in the blog
python cli.py publish --source ../sidekick --media --dry-run
python cli.py publish --source ../sidekick --media --from-file output/<slug>-final.md
# or capture any already-running app: --url http://127.0.0.1:5173

# Hashnode first-time setup (OAuth browser approval, one time):
python cli.py hashnode-auth      # stores HASHNODE_MCP_* in .env
python cli.py hashnode-tools     # verify connection + list capabilities

# Auto-write without copy-paste (needs keys):
python cli.py publish --source ../sidekick --llm openai --dry-run     # OPENAI_API_KEY
python cli.py publish --source ../sidekick --llm anthropic --dry-run  # ANTHROPIC_API_KEY
python cli.py publish --source ../sidekick --llm ollama --dry-run     # local Ollama
```

Optional: any OpenAI-compatible endpoint (including self-hosted gateways) works via
`OPENAI_BASE_URL` + `OPENAI_MODEL` — the `--llm openai` provider is just HTTP.

## Inside opencode

Slash command + agent live in `.opencode/`:

- `/publish-work ../sidekick` — full prompt-to-publish flow using your current model
- agent `work-blogger` — same rules as a subagent

## What each target does

| Target | Method | Needs |
|---|---|---|
| dev.to | `POST /api/articles` (needs a browser-like `User-Agent` — bots get empty 403s) | `DEVTO_API_KEY` (settings → extensions) |
| Hashnode | Official MCP server (`mcp.hashnode.com/mcp`) via `publisher/hashnode_mcp.py`. **Writes require a Pro plan** (free API retired May 2026, verified: server returns `FORBIDDEN` without Pro). Publication ID auto-discovered from `list_publications` | `python cli.py hashnode-auth` (OAuth, one time) |
| Hashnode (free) | Dashboard → new post → **import from URL**, paste the dev.to link. Pulls content + sets canonical automatically | nothing |
| Medium | export + import-story (API deprecated, honest fallback) | nothing |
| LinkedIn | **full native post** (story + detail + lesson, links at end) as copy-paste draft; demo video attached manually | nothing |
| X | **native thread** (hook + one idea per tweet, ≤280 chars checked) as copy-paste draft; video attached to tweet 1. Auto-post with `--live` if `X_*` creds exist (OAuth 1.0a, chunked video upload, reply-chain thread). Free X API is read-only — 401/403/429 degrade to the draft file, never a crash | nothing (or `X_API_KEY/SECRET + X_ACCESS_TOKEN/SECRET`) |

## Platform voices

One source, three shapes (`generator/templates.py`): the **blog** is long-form dev-to-dev;
**LinkedIn** is a standalone professional post, never a link drop; **X** is a hook-first
thread where each tweet stands alone. The LLM prompt asks for all three at once
(`BLOG %%% LINKEDIN %%% X %%% META`); offline fallbacks generate all three from evidence.

## Demo media (`--media`, local web projects only)

`media/runner.py` starts your dev server (vite/next/npm, collision-safe port detect),
`media/capture.mjs` (Playwright + ffmpeg) screenshots 3 frames and records a ≤30s
720p mp4 of a scripted mouse sweep. Blogs get screenshots only; LinkedIn/X drafts
reference the video for manual attach. Screenshots are copied to your project's
`docs/demo/` and embedded as `raw.githubusercontent.com` URLs on your current branch —
**commit + push for them to render**. Expo/mobile: capture on-device manually.

> Hashnode free-plan reality (Sep 2026): connecting works and reads work, but
> `create_draft`/`create_post` return `FORBIDDEN` without Pro. Don't retry —
> use the import-from-URL fallback until/unless you upgrade.

## Authenticity guardrails

- `ingest/resolver.py` is the only source of truth (README, manifests, file tree, git log, GitHub API).
- `generator/templates.py` bans hype (`revolutionary`, `game-changer`…) and forces a *what broke* section.
- Thin evidence → short post + `[FILL IN]` markers, never padded.
- `output/history.json` blocks accidental double-posts.
