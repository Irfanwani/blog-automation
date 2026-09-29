"""Hashnode publisher via official MCP server (mcp.hashnode.com/mcp).

Free GraphQL API was retired May 2026 — this replaced it. Auth = OAuth
browser approval (python cli.py hashnode-auth), writes need a Pro plan.

Flow: connect -> tools/list -> auto-pick create/draft tool -> call with
schema-mapped args. If HASHNODE_PUBLICATION_ID is unset, tries to discover
it from a user/me tool first.
"""
from __future__ import annotations

import os
import re
import time

from publisher.hashnode_mcp import HashnodeMCP, find_tool, map_args, MCPError


def _token() -> str:
    tok = os.environ.get("HASHNODE_MCP_TOKEN", "")
    exp = os.environ.get("HASHNODE_MCP_EXPIRY", "0")
    if tok and exp.isdigit() and int(exp) - time.time() < 300:
        from publisher.hashnode_auth import refresh
        try:
            tok = refresh()
        except Exception:
            pass
    return tok


def _discover_pub_id(mcp: HashnodeMCP, tools: list[dict]) -> str:
    me_tool = find_tool(tools, ["me", "user", "profile", "whoami"])
    if not me_tool:
        return ""
    try:
        out = mcp.call(me_tool["name"], {})
        blob = str(out)
        m = re.search(r"\b([0-9a-f]{24})\b", blob)
        return m.group(1) if m else ""
    except MCPError:
        return ""


def publish(title: str, markdown: str, tags: list[str], cover_url: str = "", draft: bool = True) -> dict:
    token = _token()
    if not token:
        return {"ok": False, "error": "Not connected. Run: python cli.py hashnode-auth"}
    try:
        mcp = HashnodeMCP(token)
        mcp.connect()
        tools = mcp.tools()
    except MCPError as e:
        return {"ok": False, "error": f"MCP connect failed: {e}. Re-run hashnode-auth?"}

    pub_id = os.environ.get("HASHNODE_PUBLICATION_ID", "")
    if not pub_id:
        pub_id = _discover_pub_id(mcp, tools)

    tool = (find_tool(tools, ["draft", "create"], ["post", "article", "draft"]) or
            find_tool(tools, ["create"], ["post", "article"]) or
            find_tool(tools, ["publish"], ["post", "article"]))
    if not tool:
        names = [t.get("name") for t in tools]
        return {"ok": False, "error": f"No create/publish tool found. Available: {names}"}
    schema = tool.get("inputSchema", {}).get("properties", {})
    args = map_args(schema, title, markdown, tags or ["showdev"], pub_id)
    if cover_url:
        for k in schema:
            if "cover" in k.lower() or "image" in k.lower():
                args[k] = cover_url
                break
    try:
        out = mcp.call(tool["name"], args)
        return {"ok": True, "tool": tool["name"], "result": str(out)[:500]}
    except MCPError as e:
        return {"ok": False, "error": str(e)[:500]}


def list_tools() -> dict:
    token = _token()
    if not token:
        return {"ok": False, "error": "Not connected. Run: python cli.py hashnode-auth"}
    try:
        mcp = HashnodeMCP(token)
        mcp.connect()
        tools = mcp.tools()
        return {"ok": True, "tools": [
            {"name": t.get("name"), "description": (t.get("description") or "")[:150]} for t in tools]}
    except MCPError as e:
        return {"ok": False, "error": str(e)[:300]}
