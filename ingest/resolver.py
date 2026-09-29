"""Resolve a work source into an evidence-backed ProjectContext.

Accepted --source forms:
  1. local path   e.g. ../sidekick  /abs/path  ./portfolio
  2. github url   e.g. https://github.com/owner/repo  (optional @branch, /tree/branch)
  3. free text    e.g. "Built a geotag camera app with offline maps..."

Rule: never invent. Everything downstream must cite this context only.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
GITHUB_RE = re.compile(
    r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "Pods", ".expo"}
TEXT_EXTS = {".md", ".json", ".js", ".ts", ".tsx", ".py", ".swift", ".kt", ".go", ".rs", ".toml", ".yaml", ".yml"}
MAX_FILE_BYTES = 6000
MAX_FILES = 12


@dataclass
class ProjectContext:
    title: str
    source_type: str  # local | github | text
    source_ref: str
    repo_url: str = ""
    description_raw: str = ""
    readme: str = ""
    tech_stack: list[str] = field(default_factory=list)
    file_tree: str = ""
    key_files: dict[str, str] = field(default_factory=dict)
    commits: list[str] = field(default_factory=list)
    github_meta: dict = field(default_factory=dict)

    def evidence_pack(self) -> str:
        parts = [
            f"# PROJECT EVIDENCE (ground truth — do not invent beyond this)",
            f"source_type: {self.source_type}",
            f"source_ref: {self.source_ref}",
            f"repo_url: {self.repo_url or 'n/a'}",
            f"tech_stack: {', '.join(self.tech_stack) or 'unknown'}",
            "",
            "## description_raw",
            self.description_raw or "(none)",
            "",
            "## README (truncated)",
            self.readme[:8000] or "(none)",
            "",
            "## file_tree (truncated)",
            self.file_tree[:4000] or "(none)",
            "",
            "## recent_commits",
            "\n".join(f"- {c}" for c in self.commits[:10]) or "(none)",
            "",
            "## github_meta",
            json.dumps(self.github_meta, indent=2)[:2000] if self.github_meta else "(none)",
        ]
        for name, content in list(self.key_files.items())[:MAX_FILES]:
            parts += ["", f"## file: {name}", content[:MAX_FILE_BYTES]]
        return "\n".join(parts)


def resolve(source: str) -> ProjectContext:
    source = source.strip()
    if os.path.exists(os.path.expanduser(source)):
        return _from_local(source)
    m = GITHUB_RE.search(source)
    if m or source.startswith("git@github.com"):
        owner, repo = _parse_github(source)
        return _from_github(owner, repo, source)
    return _from_text(source)


def _parse_github(source: str) -> tuple[str, str]:
    if source.startswith("git@"):
        part = source.split(":", 1)[1].removesuffix(".git").strip()
        owner, repo = part.split("/")[:2]
        return owner, repo
    m = GITHUB_RE.search(source)
    assert m, f"Unparseable github url: {source}"
    return m.group("owner"), m.group("repo")


# --- local ---

def _from_local(path: str) -> ProjectContext:
    path = os.path.abspath(os.path.expanduser(path))
    title = os.path.basename(path.rstrip("/"))
    readme = _read_readme(path)
    tree = _file_tree(path)
    key_files = _key_files(path)
    tech = _detect_stack(path, key_files)
    commits = _git_log(path)
    desc = (readme.splitlines()[0] if readme else "")[:300]
    return ProjectContext(
        title=title, source_type="local", source_ref=path,
        repo_url=_git_remote(path),
        description_raw=desc, readme=readme, tech_stack=tech,
        file_tree=tree, key_files=key_files, commits=commits,
    )


def _read_readme(path: str) -> str:
    for name in ("README.md", "readme.md", "README.MD", "README.txt", "README"):
        p = os.path.join(path, name)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    return f.read()[:12000]
            except OSError:
                pass
    return ""


def _file_tree(path: str, max_entries: int = 120) -> str:
    out: list[str] = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        rel = os.path.relpath(root, path)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 3:
            dirs[:] = []
            continue
        for name in sorted(files)[:40]:
            if name.startswith("."):
                continue
            p = os.path.join(rel, name) if rel != "." else name
            out.append(p)
            if len(out) >= max_entries:
                return "\n".join(out)
    return "\n".join(out)


def _key_files(path: str) -> dict[str, str]:
    candidates = ["package.json", "pyproject.toml", "requirements.txt",
                  "Cargo.toml", "go.mod", "pubspec.yaml", "App.json", "app.json"]
    found: dict[str, str] = {}
    for c in candidates:
        p = os.path.join(path, c)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    found[c] = f.read()[:MAX_FILE_BYTES]
            except OSError:
                pass
    # + one small entry file for flavour
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            fp = os.path.join(root, fn)
            try:
                if ext in TEXT_EXTS and os.path.getsize(fp) < 20000 and len(found) < MAX_FILES:
                    rel = os.path.relpath(fp, path)
                    if rel not in found and "test" not in rel.lower() and "lock" not in rel.lower():
                        with open(fp, encoding="utf-8", errors="replace") as f:
                            found[rel] = f.read()[:3000]
                    if len(found) >= 5:
                        return found
            except OSError:
                continue
    return found


def _detect_stack(path: str, key_files: dict[str, str]) -> list[str]:
    stack: list[str] = []
    blob = "\n".join(key_files.values())[:20000].lower()
    names = os.listdir(path)
    checks = [
        (re.search(r"\b(react-native|expo)\b", blob) is not None, "React Native/Expo"),
        ("next" in blob, "Next.js"),
        ("flutter" in blob or "pubspec.yaml" in key_files, "Flutter"),
        ("swift" in blob or any(n.endswith(".xcodeproj") for n in names), "iOS/Swift"),
        ("kotlin" in blob, "Kotlin"),
        ("django" in blob or "fastapi" in blob or "flask" in blob, "Python backend"),
        ("typescript" in blob, "TypeScript"),
        ("three" in blob, "Three.js"),
        ("tailwind" in blob, "Tailwind"),
        ("postgres" in blob or "supabase" in blob, "Postgres/Supabase"),
    ]
    for cond, label in checks:
        if cond:
            stack.append(label)
    for fn in ("package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"):
        if fn in key_files and fn not in " ".join(stack).lower():
            pass
    if os.path.isfile(os.path.join(path, "package.json")) and "React Native/Expo" not in stack:
        stack.append("Node.js")
    return stack[:8]


def _git_remote(path: str) -> str:
    try:
        r = subprocess.run(["git", "-C", path, "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=10)
        url = r.stdout.strip()
        if url.endswith(".git"):
            url = url[:-4]
        if url.startswith("git@"):
            url = "https://" + url[4:].replace(":", "/", 1)
        return url
    except (OSError, subprocess.SubprocessError):
        return ""


def _git_log(path: str, n: int = 8) -> list[str]:
    try:
        r = subprocess.run(["git", "-C", path, "log", f"-n{n}", "--oneline"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    return []


# --- github ---

def _gh_get(url: str) -> dict | str | None:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "work-presence/0.1",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return body
    except Exception:
        return None


def _from_github(owner: str, repo: str, ref: str) -> ProjectContext:
    meta = _gh_get(f"https://api.github.com/repos/{owner}/{repo}") or {}
    readme_b64 = ""
    rd = _gh_get(f"https://api.github.com/repos/{owner}/{repo}/readme")
    if isinstance(rd, dict) and rd.get("content"):
        try:
            readme_b64 = base64.b64decode(rd["content"]).decode("utf-8", errors="replace")[:12000]
        except Exception:
            pass
    tech = [l for l in [meta.get("language")] if l]
    topics = meta.get("topics", []) if isinstance(meta, dict) else []
    return ProjectContext(
        title=repo, source_type="github", source_ref=ref,
        repo_url=f"https://github.com/{owner}/{repo}",
        description_raw=(meta.get("description") or "") if isinstance(meta, dict) else "",
        readme=readme_b64, tech_stack=(tech + topics)[:8],
        github_meta={k: meta.get(k) for k in ("stars", "stargazers_count", "forks_count", "language", "description", "html_url") if isinstance(meta, dict)} if isinstance(meta, dict) else {},
    )


def _from_text(text: str) -> ProjectContext:
    title = text.split(".")[0].split("\n")[0][:60].strip() or "My project"
    return ProjectContext(
        title=title, source_type="text", source_ref="(pasted description)",
        description_raw=text[:4000],
    )
