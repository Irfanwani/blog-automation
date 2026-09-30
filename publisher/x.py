"""X/Twitter: thread as copy-paste draft + video file.

Honest note: X's free API tier is READ-ONLY. Posting via API needs a paid
tier (historically ~$100/mo Basic), which is absurd for occasional work
posts. So X is draft-file based like LinkedIn: copy the thread, attach the
demo video, post. No bans, no bill.
"""
from __future__ import annotations

import os
import re


def split_tweets(thread: str) -> list[str]:
    thread = thread.strip()
    if re.search(r"^\d+/", thread, re.M):
        parts = re.split(r"(?=^\d+/\s?)", thread, flags=re.M)
        return [p.strip() for p in parts if p.strip()]
    # fallback: split on blank lines into <=280 char chunks
    tweets: list[str] = []
    for para in thread.split("\n\n"):
        para = para.strip()
        while len(para) > 280:
            cut = para.rfind(" ", 0, 277)
            cut = cut if cut > 0 else 277
            tweets.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            tweets.append(para)
    return tweets


def save_thread(thread: str, out_dir: str, slug: str, video: str = "") -> dict:
    tweets = split_tweets(thread)
    over = [(i + 1, len(t)) for i, t in enumerate(tweets) if len(t) > 280]
    lines: list[str] = []
    for i, t in enumerate(tweets, 1):
        lines += [f"─── tweet {i}/{len(tweets)} ({len(t)} chars) ───", t, ""]
    if video:
        lines += [f"[ATTACH VIDEO to tweet 1: {os.path.basename(video)}]", ""]
    if over:
        lines += ["[WARN over 280 chars: " + ", ".join(f"#{i} ({n})" for i, n in over) + " — trim before posting]", ""]
    path = os.path.join(out_dir, f"{slug}-x.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return {"ok": True, "path": path, "tweets": len(tweets), "over": over}
