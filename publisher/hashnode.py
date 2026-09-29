"""Hashnode publisher — https://gql.hashnode.com/ publishPost"""
from __future__ import annotations

import json
import os
import urllib.request

MUTATION = """mutation Publish($input: PublishPostInput!) {
  publishPost(input: $input) { post { url slug } }
}"""


def publish(title: str, markdown: str, tags: list[str], cover_url: str = "", draft: bool = True) -> dict:
    token = os.environ.get("HASHNODE_TOKEN")
    pub_id = os.environ.get("HASHNODE_PUBLICATION_ID")
    if not token or not pub_id:
        return {"ok": False, "error": "HASHNODE_TOKEN / HASHNODE_PUBLICATION_ID not set"}
    # Hashnode wants tag objects; keep it minimal with slugs
    payload = {"query": MUTATION, "variables": {"input": {
        "publicationId": pub_id, "title": title, "contentMarkdown": markdown,
        "tags": [{"slug": t.lower().replace(".", "")} for t in (tags or ["showdev"])[:4]],
    }}}
    if cover_url:
        payload["variables"]["input"]["coverImageOptions"] = {"coverImageURL": cover_url}
    req = urllib.request.Request(
        "https://gql.hashnode.com/", data=json.dumps(payload).encode(),
        headers={"Authorization": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
            if body.get("errors"):
                return {"ok": False, "error": str(body["errors"])[:500]}
            post = body["data"]["publishPost"]["post"]
            return {"ok": True, "url": post.get("url")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500]}
