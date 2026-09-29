"""Append-only publish history (prevents double-posting the same project)."""
from __future__ import annotations

import json
import os
import time


def record(out_dir: str, entry: dict) -> None:
    path = os.path.join(out_dir, "history.json")
    hist: list = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                hist = json.load(f)
        except (json.JSONDecodeError, OSError):
            hist = []
    entry["ts"] = int(time.time())
    hist.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist[-100:], f, indent=2)
