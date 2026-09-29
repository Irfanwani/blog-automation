"""LLM provider abstraction.

Default = 'opencode' (manual): no API key needed. The CLI writes an evidence
pack + copy-paste prompt; you run it in opencode with any free model
(Muse Spark etc.) and paste the markdown back. This is the recommended
authentic-work flow — you review before publishing.

Optional auto providers (need keys): openai (or any OpenAI-compatible base
url), anthropic, ollama. Select with --llm <name>.
"""
from __future__ import annotations

import json
import os
import urllib.request


class LLMError(RuntimeError):
    pass


def generate(provider: str, system: str, user: str, max_tokens: int = 3000) -> str:
    provider = provider.lower().strip()
    if provider == "openai":
        return _openai(system, user, max_tokens)
    if provider == "anthropic":
        return _anthropic(system, user, max_tokens)
    if provider == "ollama":
        return _ollama(system, user)
    if provider == "opencode":
        raise LLMError("opencode-manual")
    raise LLMError(f"Unknown llm provider: {provider}")


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise LLMError(f"LLM request failed: {e}") from e


def _openai(system: str, user: str, max_tokens: int) -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("OPENAI_API_KEY not set")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    out = _post_json(f"{base}/chat/completions", {
        "model": model, "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        return out["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenAI response: {out}") from e


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY not set")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
    out = _post_json("https://api.anthropic.com/v1/messages", {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": user}],
    }, {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"})
    try:
        return "".join(b.get("text", "") for b in out["content"])
    except KeyError as e:
        raise LLMError(f"Unexpected Anthropic response: {out}") from e


def _ollama(system: str, user: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    out = _post_json(f"{host}/api/chat", {
        "model": model, "stream": False,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }, {"Content-Type": "application/json"}, timeout=300)
    try:
        return out["message"]["content"]
    except KeyError as e:
        raise LLMError(f"Unexpected Ollama response: {out}") from e
