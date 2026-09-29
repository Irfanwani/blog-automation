"""Minimal MCP Streamable-HTTP client (stdlib only) for Hashnode's MCP server.

Speaks JSON-RPC over POST https://mcp.hashnode.com/mcp:
initialize -> notifications/initialized -> tools/list -> tools/call.
Handles both plain-JSON and SSE responses. No third-party deps.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error

MCP_URL = "https://mcp.hashnode.com/mcp"
PROTOCOL = "2025-06-18"


class MCPError(RuntimeError):
    pass


def _parse_response(resp) -> dict | None:
    ctype = resp.headers.get("Content-Type", "")
    raw = resp.read().decode("utf-8", errors="replace")
    if "event-stream" in ctype:
        for line in raw.splitlines():
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
        return None
    if not raw.strip():
        return None
    return json.loads(raw)


def _post(token: str, payload: dict | None, session: str = "") -> tuple[dict | None, str]:
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "Authorization": f"Bearer {token}",
               "User-Agent": "work-presence/0.1"}
    if session:
        headers["mcp-session-id"] = session
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(MCP_URL, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return _parse_response(r), r.headers.get("mcp-session-id", session)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:300]
        except Exception:
            detail = ""
        raise MCPError(f"MCP HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise MCPError(f"MCP request failed: {e}") from e


class HashnodeMCP:
    def __init__(self, token: str):
        self.token = token
        self.session = ""

    def _rpc(self, method: str, params: dict | None = None, req_id: int = 1) -> dict:
        payload: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            payload["params"] = params
        out, self.session = _post(self.token, payload, self.session)
        if not out:
            raise MCPError(f"No response for {method}")
        if out.get("error"):
            raise MCPError(f"{method}: {out['error']}")
        return out.get("result", {})

    def connect(self) -> dict:
        res = self._rpc("initialize", {"protocolVersion": PROTOCOL,
                                       "capabilities": {},
                                       "clientInfo": {"name": "work-presence", "version": "0.1.0"}})
        _post(self.token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, self.session)
        return res

    def tools(self) -> list[dict]:
        return self._rpc("tools/list", {}, 2).get("tools", [])

    def call(self, name: str, arguments: dict) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments}, 3)


def find_tool(tools: list[dict], *keywords: str) -> dict | None:
    """First tool whose name/description matches ALL keyword groups (OR within group)."""
    for t in tools:
        hay = f"{t.get('name','')} {t.get('description','')}".lower()
        if all(any(k in hay for k in group) for group in keywords):
            return t
    return None


def map_args(schema_props: dict, title: str, markdown: str,
             tags: list[str], pub_id: str, draft: bool = True) -> dict:
    """Map our fields onto whatever property names the tool schema uses."""
    names = {p.lower(): p for p in schema_props}
    args: dict = {}

    def pick(*cands: str) -> str:
        for c in cands:
            for low, real in names.items():
                if c in low:
                    return real
        return ""

    if (k := pick("title", "headline", "name")):
        args[k] = title
    md_key = pick("contentmarkdown", "content_markdown", "markdown", "content", "body")
    if md_key:
        args[md_key] = markdown
    if (k := pick("tags", "tag")):
        prop = schema_props.get(names[k.lower()], {})
        items = prop.get("items", {})
        if isinstance(items, dict) and items.get("type") == "object":
            args[k] = [{"slug": t.lower().replace(".", "")} for t in tags]
        else:
            args[k] = tags
    if pub_id and (k := pick("publication", "publicationid", "blog")):
        args[k] = pub_id
    if (k := pick("isdraft", "is_draft", "draft")):
        prop = schema_props.get(names[k.lower()], {})
        if prop.get("type") == "boolean":
            args[k] = draft
    elif (k := pick("publish", "published", "status", "visibility")):
        prop = schema_props.get(names[k.lower()], {})
        if prop.get("type") == "boolean":
            args[k] = not draft
    return args
