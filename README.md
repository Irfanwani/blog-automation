# work-presence — work-only tech presence, no fake content

Prompt with a **local path, GitHub URL, or description** → get an evidence-backed blog → publish to **dev.to + Hashnode** (API), **Medium** (1-click import, API is deprecated), and a **LinkedIn copy-paste draft** linking the blog.

## Quickstart

```bash
cd work-presence
cp .env.example .env   # fill DEVTO_API_KEY, HASHNODE_TOKEN, HASHNODE_PUBLICATION_ID

# 1. Dry run — works with ZERO keys, uses opencode-native flow
python cli.py publish --source ../sidekick --dry-run
python cli.py publish --source https://github.com/owner/repo --dry-run
python cli.py publish --source "Built offline-first geotag camera with ..." --dry-run

# 2. Write the real post in opencode (any free model, e.g. Muse Spark):
#    open output/<slug>-PROMPT.md, paste into chat, save answer to output/<slug>-final.md

# 3. Publish (asks nothing, posts as drafts by default)
python cli.py publish --source ../sidekick --from-file output/<slug>-final.md
python cli.py publish --source ../sidekick --from-file output/<slug>-final.md --live  # public, not draft

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
| dev.to | `POST /api/articles` | `DEVTO_API_KEY` (settings → extensions) |
| Hashnode | `gql.hashnode.com publishPost` | `HASHNODE_TOKEN` + `HASHNODE_PUBLICATION_ID` |
| Medium | export + import-story (API deprecated, honest fallback) | nothing |
| LinkedIn | `output/<slug>-linkedin.txt` copy-paste draft (API needs app review; this avoids bans) | nothing |

## Authenticity guardrails

- `ingest/resolver.py` is the only source of truth (README, manifests, file tree, git log, GitHub API).
- `generator/templates.py` bans hype (`revolutionary`, `game-changer`…) and forces a *what broke* section.
- Thin evidence → short post + `[FILL IN]` markers, never padded.
- `output/history.json` blocks accidental double-posts.
