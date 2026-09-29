"""Medium has no stable public write API (integration tokens deprecated 2024+).
Strategy: export a Medium-ready file + 3-click import instructions. Honest > hacky."""
from __future__ import annotations

import os


def export(title: str, markdown: str, out_dir: str, slug: str) -> dict:
    path = os.path.join(out_dir, f"{slug}-medium.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{markdown}")
    instructions = (
        "Medium import: medium.com -> Write -> ⋯ -> Import story -> paste the "
        "published dev.to/Hashnode URL (sets canonical), or paste this file."
    )
    return {"ok": True, "path": path, "instructions": instructions}
