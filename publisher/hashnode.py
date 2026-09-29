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
    owned = [t for t in tools if "list_publication" in t.get("name", "")]
    if owned:
        try:
            out = mcp.call(owned[0]["name"], {})
            ids = re.findall(r"\b([0-9a-f]{24})\b", str(out))
            if ids:
                return ids[0]
        except MCPError:
            pass
    me_tool = find_tool(tools, ["me", "user", "profile", "whoami"])
    if not me_tool:
        return ""
    try:
        out = mcp.call(me_tool["name"], {})
        m = re.search(r"\b([0-9a-f]{24})\b", str(out))
        return m.group(1) if m else ""
    except MCPError:
        return ""


def publish(title: str, markdown: str, tags: list[str], cover_url: str = "", draft: bool = True,
            canonical: str = "") -> dict:
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
        if pub_id:
            try:
                from publisher.hashnode_auth import _upsert_env
                _upsert_env({"HASHNODE_PUBLICATION_ID": pub_id})
                print(f"[hashnode] discovered publication id, saved to .env")
            except Exception:
                pass

    if draft:
        tool = (find_tool(tools, ["draft"], ["create", "save", "new"]) or
                find_tool(tools, ["create"], ["draft"]))
    else:
        tool = find_tool(tools, ["create"], ["post", "article"])
    if not tool:
        tool = (find_tool(tools, ["draft", "create"], ["post", "article", "draft"]) or
                find_tool(tools, ["create"], ["post", "article"]) or
                find_tool(tools, ["publish"], ["post", "article"]))
    if not tool:
        names = [t.get("name") for t in tools]
        return {"ok": False, "error": f"No create/publish tool found. Available: {names}"}
    schema = tool.get("inputSchema", {}).get("properties", {})
    args = map_args(schema, title, markdown, tags or ["showdev"], pub_id, draft)
    if cover_url:
        for k in schema:
            if "cover" in k.lower() or "image" in k.lower():
                args[k] = cover_url
                break
    if canonical:
        for k in schema:
            if "original" in k.lower() and "url" in k.lower():
                args[k] = canonical
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
