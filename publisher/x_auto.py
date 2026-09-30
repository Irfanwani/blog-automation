"""X auto-post: thread + video via API (stdlib only, OAuth 1.0a user context).

Needs (developer.x.com -> project/app with Read+Write, then access tokens):
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET

EVERY failure mode returns {"ok": False, "error": ...} — never raises.
Free-tier accounts get read-only keys: POST returns 401/403 and we say so
plainly instead of crashing the run.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error

UA = {"User-Agent": "work-presence/0.1"}
TWEETS_URL = "https://api.x.com/2/tweets"
UPLOAD_URL = "https://upload.x.com/1.1/media/upload.json"


def creds() -> dict:
    return {k: os.environ.get(k, "") for k in
            ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")}


def have_creds() -> bool:
    return all(creds().values())


def _oauth_header(method: str, url: str, params: dict, c: dict) -> str:
    import random
    oauth = {"oauth_consumer_key": c["X_API_KEY"], "oauth_nonce": hashlib.md5(
        f"{time.time()}{random.random()}".encode()).hexdigest(),
        "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())),
        "oauth_token": c["X_ACCESS_TOKEN"], "oauth_version": "1.0"}
    base = {**params, **oauth}
    enc = lambda s: urllib.parse.quote(str(s), safe="")
    param_str = "&".join(f"{enc(k)}={enc(v)}" for k, v in sorted(base.items()))
    sig_base = "&".join([method.upper(), enc(url.split("?")[0]), enc(param_str)])
    key = f"{enc(c['X_API_SECRET'])}&{enc(c['X_ACCESS_SECRET'])}"
    sig = base64.b64encode(hmac.new(key.encode(), sig_base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(oauth.items()))


def _api(method: str, url: str, c: dict, body: dict | None = None,
         query: dict | None = None) -> tuple[int, dict | str]:
    """Returns (status, parsed_json_or_text). Never raises."""
    q = ("?" + urllib.parse.urlencode(query)) if query else ""
    data = json.dumps(body).encode() if body is not None else None
    headers = {**UA, "Authorization": _oauth_header(method, url, {**(query or {})}, c)}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url + q, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:400]
        except Exception:
            detail = ""
        return e.code, detail
    except Exception as e:
        return 0, str(e)[:200]


def _friendly(status: int, detail: object) -> str:
    d = str(detail)
    if status == 401:
        return "X auth rejected (401) — bad/expired tokens. Regenerate at developer.x.com."
    if status == 403:
        if "read-only" in d.lower() or "not allowed" in d.lower() or "restricted" in d.lower() or not d.strip():
            return ("X refused to post (403) — free-tier keys are READ-ONLY. "
                    "Upgrade the app tier or keep using the copy-paste draft. Nothing was posted.")
        return f"X refused (403): {d[:200]}"
    if status == 429:
        return "X rate limit (429) — try again in ~15 min. Nothing was posted."
    if status == 0:
        return f"X network error: {d}. Nothing was posted."
    return f"X HTTP {status}: {d[:200]}"


def upload_video(path: str, c: dict) -> tuple[str, str]:
    """Chunked video upload. Returns (media_id, error)."""
    size = os.path.getsize(path)
    if size > 512 * 1024 * 1024:
        return "", "video over X's 512MB limit"
    st, out = _api("POST", UPLOAD_URL, c, query={
        "command": "INIT", "media_type": "video/mp4",
        "media_category": "tweet_video", "total_bytes": str(size)})
    if st != 202 or not isinstance(out, dict) or "media_id_string" not in out:
        return "", _friendly(st, out)
    mid = out["media_id_string"]
    with open(path, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            boundary = "wpm" + hashlib.md5(os.urandom(8)).hexdigest()
            parts = [
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"command\"\r\n\r\nAPPEND\r\n",
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"media_id\"\r\n\r\n{mid}\r\n",
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"segment_index\"\r\n\r\n{idx}\r\n",
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"; filename=\"d.mp4\"\r\n"
                "Content-Type: video/mp4\r\n\r\n",
            ]
            body = b"".join(p.encode() for p in parts) + chunk + f"\r\n--{boundary}--\r\n".encode()
            headers = {**UA, "Authorization": _oauth_header("POST", UPLOAD_URL, {}, c),
                       "Content-Type": f"multipart/form-data; boundary={boundary}"}
            req = urllib.request.Request(UPLOAD_URL, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    if r.status not in (200, 201, 204):
                        return "", f"video chunk {idx} upload HTTP {r.status}"
            except Exception as e:
                return "", f"video chunk {idx} failed: {str(e)[:150]}"
            idx += 1
    st, out = _api("POST", UPLOAD_URL, c, query={"command": "FINALIZE", "media_id": mid})
    if st not in (200, 201):
        return "", _friendly(st, out)
    for _ in range(30):  # wait for async processing (video needs it)
        st, out = _api("GET", UPLOAD_URL, c, query={"command": "STATUS", "media_id": mid})
        try:
            state = out["processing_info"]["state"]  # type: ignore[index]
        except (TypeError, KeyError):
            return mid, ""
        if state == "succeeded":
            return mid, ""
        if state == "failed":
            return "", f"X video processing failed: {out}"
        time.sleep(5)
    return "", "X video processing timed out (uploaded, not attached)"


def post_thread(tweets: list[str], video: str = "") -> dict:
    """Post tweets as a reply-chain thread. Video (if any) on tweet 1."""
    c = creds()
    if not all(c.values()):
        missing = [k for k, v in c.items() if not v]
        return {"ok": False, "error": f"X creds missing: {missing}. Draft file is the fallback."}
    media_id = ""
    if video and os.path.isfile(video):
        media_id, err = upload_video(video, c)
        if err and "timed out" not in err and "processing" not in err:
            return {"ok": False, "error": err}
        if err:
            print(f"[x] warning: {err} — posting text-only.", flush=True)
            media_id = ""
    reply_to = ""
    first_id, first_url = "", ""
    for i, text in enumerate(tweets):
        body: dict = {"text": text[:280]}
        if i == 0 and media_id:
            body["media"] = {"media_ids": [media_id]}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        st, out = _api("POST", TWEETS_URL, c, body)
        if st not in (200, 201) or not isinstance(out, dict) or "data" not in out:
            return {"ok": False, "error": _friendly(st, out),
                    "posted": i, "first_url": first_url}
        reply_to = out["data"]["id"]
        if i == 0:
            first_id = reply_to
            try:
                who = out["data"].get("author_id", "")
                first_url = f"https://x.com/i/status/{first_id}"
            except KeyError:
                pass
    return {"ok": True, "url": first_url, "tweets_posted": len(tweets)}
