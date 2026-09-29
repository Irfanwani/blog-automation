"""dev.to publisher — https://developers.forem.com/api/v1#tag/articles"""
from __future__ import annotations

import json
import os
import urllib.request


UA = {"User-Agent": "work-presence/0.1 (+local cli)",
      "Accept": "application/vnd.forem.api-v1+json"}


def publish(title: str, markdown: str, tags: list[str], canonical: str = "", draft: bool = True) -> dict:
    key = os.environ.get("DEVTO_API_KEY")
    if not key:
        return {"ok": False, "error": "DEVTO_API_KEY not set"}
    payload: dict = {"article": {
        "title": title, "body_markdown": markdown,
        "tags": (tags or ["showdev"])[:4], "published": not draft,
    }}
    if canonical:
        payload["article"]["canonical_url"] = canonical
    req = urllib.request.Request(
        "https://dev.to/api/articles", data=json.dumps(payload).encode(),
        headers={"api-key": key, "Content-Type": "application/json", **UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
            return {"ok": True, "url": body.get("url") or body.get("canonical_url"), "id": body.get("id")}
    except Exception as e:
        status = getattr(e, "code", "?")
        try:
            detail = e.read().decode()  # type: ignore[attr-defined]
        except Exception:
            detail = str(e)
        return {"ok": False, "error": f"HTTP {status}: {detail[:300]}"}
