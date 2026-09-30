"""Start a local dev server for a project dir. Supports vite / next / generic npm.
Returns (Popen, url). Caller must proc.terminate(). Expo/mobile: returns instructions.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request

CANDIDATE_PORTS = [5173, 5174, 3000, 3001, 8080, 8081, 19006]


def detect(project_dir: str) -> dict:
    info: dict = {"kind": "unknown", "start": None}
    pkg = os.path.join(project_dir, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        scripts = data.get("scripts", {})
        if "expo" in deps:
            info.update(kind="expo", start=None,
                        note="Expo needs a simulator/emulator — capture on device manually.")
        elif "vite" in deps or os.path.exists(os.path.join(project_dir, "vite.config.js")) or \
                os.path.exists(os.path.join(project_dir, "vite.config.ts")):
            info.update(kind="vite", start=["npm", "run", "dev", "--", "--host", "127.0.0.1"])
        elif "next" in deps:
            info.update(kind="next", start=["npm", "run", "dev", "--", "-H", "127.0.0.1"])
        elif "dev" in scripts:
            info.update(kind="npm", start=["npm", "run", "dev"])
    return info


def _port_open(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def start(project_dir: str, timeout: int = 60) -> tuple:
    info = detect(project_dir)
    if not info["start"]:
        raise RuntimeError(info.get("note", "No runnable web dev server detected. Use --url <running-app-url>."))
    import select
    baseline = {p for p in CANDIDATE_PORTS if _port_open(p)}
    proc = subprocess.Popen(info["start"], cwd=project_dir,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out: list[str] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            rest = proc.stdout.read() if proc.stdout else ""
            raise RuntimeError(f"dev server exited:\n{(rest or '')[-1500:]}")
        # (a) prefer the URL the server itself prints (immune to port collisions)
        if proc.stdout and select.select([proc.stdout], [], [], 0)[0]:
            line = proc.stdout.readline()
            out.append(line)
            m = re.search(r"Local:\s+(http://\S+)", line)
            if m:
                return proc, m.group(1).rstrip("/"), info["kind"]
        else:
            # (b) a newly opened port that wasn't busy before we started
            for p in CANDIDATE_PORTS:
                if p not in baseline and _port_open(p):
                    return proc, f"http://127.0.0.1:{p}", info["kind"]
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("dev server did not open a port in time.\n" + "".join(out)[-1500:])
