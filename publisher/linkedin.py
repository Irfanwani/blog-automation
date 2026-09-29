"""LinkedIn: copy-paste draft (recommended). Direct API needs a verified
developer app + OAuth + w_member_social scope; most devs get rejected or
flagged for automation. Draft file avoids that entirely."""
from __future__ import annotations

import os
import re

MAX_LEN = 2900


def build_draft(hook: str, bullets: list[str], blog_url: str, tags: list[str], out_dir: str, slug: str) -> dict:
    tag_str = " ".join(f"#{t}" for t in (tags or ["buildinpublic"])[:3])
    lines = [hook.strip(), "", "What I actually did:"]
    lines += [f"→ {b.strip()}" for b in bullets[:3]]
    lines += ["", f"Full write-up: {blog_url or '<paste blog URL after publishing>'}", "", tag_str]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)[:MAX_LEN]
    path = os.path.join(out_dir, f"{slug}-linkedin.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {"ok": True, "path": path, "chars": len(text)}
