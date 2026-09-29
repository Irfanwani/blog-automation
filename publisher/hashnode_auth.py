"""OAuth 2.1 + PKCE login for Hashnode's MCP server (stdlib only).

Usage:  python cli.py hashnode-auth
Opens the browser on Hashnode's approve page, catches the redirect on
loopback, exchanges the code, and stores tokens in .env:
  HASHNODE_MCP_TOKEN / HASHNODE_MCP_REFRESH / HASHNODE_MCP_EXPIRY / HASHNODE_MCP_CLIENT_ID

Writes require a Pro publication; reads may work without.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

REGISTER_URL = "https://mcp.hashnode.com/register"
AUTH_URL = "https://mcp.hashnode.com/authorize"
TOKEN_URL = "https://mcp.hashnode.com/token"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _post_json(url: str, payload: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _post_form(url: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _upsert_env(values: dict) -> None:
    lines: list[str] = []
    if os.path.isfile(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.read().splitlines()
    seen = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, val in values.items():
        if key not in seen:
            out.append(f"{key}={val}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def run() -> dict:
    import time
    verifier = _b64url(secrets.token_bytes(48))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = _b64url(secrets.token_bytes(16))
    redirect = f"http://127.0.0.1:{CALLBACK_PORT}{CALLBACK_PATH}"

    reg = _post_json(REGISTER_URL, {
        "client_name": "work-presence-cli",
        "redirect_uris": [redirect],
        "grant_types": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_method": "none",
    })
    client_id = reg["client_id"]
    print(f"[auth] registered client {client_id[:12]}…")

    code_box: dict = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_box.update(q)
            done.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            ok = "code" in q
            self.wfile.write(
                f"<h1>{'Connected — back to terminal' if ok else 'Failed — no code received'}</h1>".encode())

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    params = {"response_type": "code", "client_id": client_id,
              "redirect_uri": redirect, "code_challenge": challenge,
              "code_challenge_method": "S256", "state": state}
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print("[auth] Opening browser — approve Hashnode access.")
    print("[auth] If it doesn't open, visit:\n ", url)
    webbrowser.open(url)
    if not done.wait(timeout=180):
        return {"ok": False, "error": "timed out waiting for browser approval"}
    server.server_close()

    code = code_box.get("code", [None])[0]
    if not code or code_box.get("state", [None])[0] != state:
        return {"ok": False, "error": f"auth failed: {code_box}"}
    tok = _post_form(TOKEN_URL, {"grant_type": "authorization_code", "code": code,
                                 "redirect_uri": redirect, "client_id": client_id,
                                 "code_verifier": verifier})
    _upsert_env({
        "HASHNODE_MCP_TOKEN": tok["access_token"],
        "HASHNODE_MCP_REFRESH": tok.get("refresh_token", ""),
        "HASHNODE_MCP_EXPIRY": str(int(time.time()) + int(tok.get("expires_in", 3600))),
        "HASHNODE_MCP_CLIENT_ID": client_id,
    })
    print("[auth] tokens saved to .env (HASHNODE_MCP_TOKEN).")
    return {"ok": True}


def refresh() -> str:
    """Refresh the access token using the stored refresh token. Returns new token."""
    import time
    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    tok = _post_form(TOKEN_URL, {"grant_type": "refresh_token",
                                 "refresh_token": env["HASHNODE_MCP_REFRESH"],
                                 "client_id": env.get("HASHNODE_MCP_CLIENT_ID", "")})
    _upsert_env({"HASHNODE_MCP_TOKEN": tok["access_token"],
                 "HASHNODE_MCP_EXPIRY": str(int(time.time()) + int(tok.get("expires_in", 3600)))})
    if tok.get("refresh_token"):
        _upsert_env({"HASHNODE_MCP_REFRESH": tok["refresh_token"]})
    return tok["access_token"]
