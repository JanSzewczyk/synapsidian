#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only facts about a project's code repository, and the next decision number of a project.

  projects.py scan --repo PATH [--docs PATH ...] [--last COMMIT] [--branch NAME] [--markdown]
  synapsidian query notes --type decision --all | projects.py decision-number --project "Project title"

`scan` prints JSON: the commit scanned, branch and origin (credentials stripped), tracked file
counts by extension and by folder (two levels), manifests (`package.json`, `pyproject.toml`,
`go.mod`, `Cargo.toml`, ... up to three folders deep) with name, version and dependency names,
the README's title, the `--docs` paths with the Markdown files under them, CI files, the last
commits, and `freshness` (D141). With --last (the hub's `scanned_commit`; --since is the old
name), also the commits and changed folders since that commit. --markdown prints the hub's
Repository block instead.

`freshness` says whether this clone may overwrite facts another clone wrote: `first` (no
--last), `same` or `ahead` (`write: true`); `behind` (HEAD is older than --last), `unknown`
(--last isn't in this clone, most likely not fetched yet) or `diverged` (`write: false`).
`off_branch` is set when --branch names another branch than the one checked out, which also
makes `write` false. `distance` counts the commits between the two.

A path inside a repository (one app of a monorepo) scans only that folder: files, commits and
changes under it. It only reads: files, plus `git rev-parse`, `ls-files`, `log`,
`diff --name-only`, `merge-base`, `rev-list --count`, `branch --show-current` and
`remote get-url` with optional locks off, so not even the index is refreshed. Nothing is
built, installed, fetched or written there (D98).

`decision-number` reads `synapsidian query` JSON on stdin and prints the project's next decision
number: one more than the highest `number` among its decisions, archived ones included, so a
number is never given twice.

Exit 2 = bad input.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit, urlunsplit

MANIFESTS = {
    "package.json", "pyproject.toml", "go.mod", "Cargo.toml", "composer.json", "Gemfile", "pom.xml",
    "build.gradle", "build.gradle.kts", "requirements.txt", "setup.py", "deno.json", "mix.exs",
    "Package.swift", "pubspec.yaml",
}  # fmt: skip
MANIFEST_SUFFIXES = (".csproj", ".sln")
CI_FILES = {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile", ".circleci/config.yml"}
# Tracked but not the project's own code: vendored or generated trees.
SKIP_PARTS = {"node_modules", "vendor", "dist", "build", ".venv", "venv", "third_party"}
MAX_MANIFEST_DEPTH = 3
LINK = re.compile(r"^\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]$")


def fail(code: int, message: str) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}))
    sys.exit(code)


# The repository's own .git/config can name programs git runs even on reads: core.fsmonitor
# runs on ls-files and diff, a pager or an external diff on log and diff. The repository is
# someone else's code (or an archive with its .git inside), so those keys are switched off.
SAFE_CONFIG = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat")
SAFE_ENV = {"GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0", "GIT_EXTERNAL_DIFF": ""}


def git(repo: Path, *args: str, check: bool = True) -> str:
    # GIT_OPTIONAL_LOCKS=0: read commands never rewrite the index's stat cache.
    if args and args[0] in ("diff", "log"):
        args = (args[0], "--no-ext-diff", "--no-textconv", *args[1:])
    proc = subprocess.run(
        ["git", *SAFE_CONFIG, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **SAFE_ENV},
    )
    if proc.returncode != 0:
        if check:
            fail(2, f"git {' '.join(args)}: {proc.stderr.strip()}")
        return ""
    return proc.stdout


def public_url(url: str) -> str:
    """The remote URL without a user or token (`https://user:token@host/x` → `https://host/x`)."""
    parts = urlsplit(url)
    if parts.scheme and "@" in parts.netloc:
        return urlunsplit(parts._replace(netloc=parts.netloc.rsplit("@", 1)[1]))
    return url


def is_url(value: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://", value, re.I)) or bool(re.match(r"^[\w.-]+@[\w.-]+:", value))


# --- manifests ----------------------------------------------------------------


def _names(deps: object) -> list[str]:
    if isinstance(deps, dict):
        return sorted(str(k) for k in deps)
    if isinstance(deps, list):  # PEP 508 strings: "pyyaml>=6.0"
        return sorted({re.split(r"[\s<>=!~;\[(]", str(d), maxsplit=1)[0] for d in deps if str(d).strip()})
    return []


def manifest_facts(path: Path) -> dict[str, Any]:
    """Name, version, description and dependency names of the manifests worth reading; others are listed only."""
    try:
        match path.name:
            case "package.json":
                data = json.loads(path.read_text(encoding="utf-8"))
                return {
                    "name": data.get("name"),
                    "version": data.get("version"),
                    "description": data.get("description"),
                    "workspaces": data.get("workspaces"),
                    "scripts": sorted(data.get("scripts") or {}),
                    "dependencies": _names(data.get("dependencies")),
                    "dev_dependencies": len(data.get("devDependencies") or {}),
                }
            case "pyproject.toml":
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                project = data.get("project") or data.get("tool", {}).get("poetry") or {}
                return {
                    "name": project.get("name"),
                    "version": project.get("version"),
                    "description": project.get("description"),
                    "requires_python": project.get("requires-python"),
                    "dependencies": _names(project.get("dependencies")),
                    "scripts": sorted(project.get("scripts") or {}),
                }
            case "Cargo.toml":
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                package = data.get("package") or {}
                return {
                    "name": package.get("name"),
                    "version": package.get("version"),
                    "description": package.get("description"),
                    "workspace": sorted((data.get("workspace") or {}).get("members") or []),
                    "dependencies": _names(data.get("dependencies")),
                }
            case "go.mod":
                text = path.read_text(encoding="utf-8")
                module = re.search(r"^module\s+(\S+)", text, re.M)
                version = re.search(r"^go\s+(\S+)", text, re.M)
                return {
                    "name": module.group(1) if module else None,
                    "go": version.group(1) if version else None,
                    "dependencies": sorted(set(re.findall(r"^\s*([\w.-]+\.[\w./-]+)\s+v\S+", text, re.M))),
                }
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return {"error": f"unreadable: {exc}"}
    return {}


# --- scan ---------------------------------------------------------------------


def freshness(repo: Path, last: str | None, branch: str | None) -> dict[str, Any]:
    """How HEAD relates to the commit the hub was last scanned at, maybe in another clone (D141)."""
    current = git(repo, "branch", "--show-current").strip() or None
    off_branch = {"expected": branch, "current": current} if branch and branch != current else None
    state, distance = "first", None
    if last:
        old = git(repo, "rev-parse", "--verify", "--quiet", f"{last}^{{commit}}", check=False).strip()
        head = git(repo, "rev-parse", "HEAD").strip()
        base = git(repo, "merge-base", old, head, check=False).strip() if old else ""
        if not old:
            state = "unknown"
        elif old == head:
            state, distance = "same", 0
        elif base == old:
            state, distance = "ahead", int(git(repo, "rev-list", "--count", f"{old}..{head}").strip())
        elif base == head:
            state, distance = "behind", int(git(repo, "rev-list", "--count", f"{head}..{old}").strip())
        else:
            state = "diverged"
    return {
        "freshness": state,
        "write": state in ("first", "same", "ahead") and off_branch is None,
        "distance": distance,
        "off_branch": off_branch,
    }


def scan(repo: Path, docs: list[str], since: str | None, branch: str | None = None) -> dict[str, Any]:
    head = git(repo, "rev-parse", "--short", "HEAD").strip()
    files = [f for f in git(repo, "ls-files", "-z").split("\0") if f]
    own = [f for f in files if not SKIP_PARTS.intersection(f.split("/")[:-1])]

    folders: Counter[str] = Counter()
    children: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for f in own:
        parts = f.split("/")
        if len(parts) > 1:
            folders[parts[0]] += 1
        if len(parts) > 2:
            children[parts[0]][parts[1]] += 1
    layout = [
        {"folder": name, "files": count, "children": [{"folder": c, "files": n} for c, n in kids.most_common(6)]}
        for name, count in folders.most_common(12)
        for kids in [children[name]]
    ]
    extensions = Counter(Path(f).suffix.lower() for f in own if Path(f).suffix)

    manifests = []
    for f in own:
        name = f.rsplit("/", 1)[-1]
        if f.count("/") < MAX_MANIFEST_DEPTH and (name in MANIFESTS or name.endswith(MANIFEST_SUFFIXES)):
            manifests.append({"path": f, **manifest_facts(repo / f)})
    manifests.sort(key=lambda m: (m["path"].count("/"), m["path"]))

    readme = next((f for f in own if "/" not in f and f.lower().startswith("readme")), None)
    readme_title = None
    if readme and (repo / readme).is_file():
        heading = re.search(r"^#\s+(.+)$", (repo / readme).read_text(encoding="utf-8", errors="replace"), re.M)
        readme_title = heading.group(1).strip() if heading else None

    doc_paths = []
    for entry in docs:
        given = Path(entry).expanduser()
        path = given if given.is_absolute() else repo / given
        inside = path.resolve().is_relative_to(repo.resolve())
        if inside:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
            notes = [f for f in own if f.endswith(".md") and (f == rel or f.startswith(rel.rstrip("/") + "/"))]
        elif path.is_dir():
            notes = sorted(str(p) for p in path.rglob("*.md"))
        else:
            notes = [str(path)] if path.is_file() else []
        doc_paths.append({"path": entry, "exists": path.exists(), "markdown": len(notes), "files": notes[:20]})

    ci = sorted(f for f in files if f.startswith(".github/workflows/") or f in CI_FILES)
    recent = commits(repo, "-10")
    result: dict[str, Any] = {
        "ok": True,
        "repo": str(repo),
        "commit": head,
        "commit_date": recent[0]["date"] if recent else None,
        "branch": git(repo, "branch", "--show-current").strip() or None,
        "origin": public_url(git(repo, "remote", "get-url", "origin", check=False).strip()) or None,
        "files": len(own),
        "extensions": dict(extensions.most_common(8)),
        "layout": layout,
        "root_files": sorted(f for f in own if "/" not in f)[:30],
        "manifests": manifests[:25],
        "readme": {"path": readme, "title": readme_title} if readme else None,
        "docs": doc_paths,
        "ci": ci[:10],
        "recent": recent,
        **freshness(repo, since, branch),
    }
    if since:
        result["since"] = changes_since(repo, since)
    return result


def commits(repo: Path, *revs: str) -> list[dict[str, str]]:
    """Commits touching the scanned folder (`-- .`), newest first, merges left out."""
    out = git(repo, "log", "--no-merges", "--format=%h%x09%cs%x09%s", *revs, "--", ".")
    return [
        {"sha": sha, "date": date, "subject": subject}
        for sha, date, subject in (line.split("\t", 2) for line in out.splitlines() if line.count("\t") >= 2)
    ]


def changes_since(repo: Path, since: str) -> dict[str, Any]:
    if not git(repo, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}", check=False).strip():
        return {"commit": since, "known": False}
    since_commits = commits(repo, f"{since}..HEAD")
    changed = [f for f in git(repo, "diff", "--name-only", "--relative", since, "HEAD", "--", ".").splitlines() if f]
    by_folder = Counter(f.split("/", 1)[0] if "/" in f else "(root)" for f in changed)
    return {
        "commit": since,
        "known": True,
        "count": len(since_commits),
        "commits": since_commits[:30],
        "changed_files": len(changed),
        "changed_folders": dict(by_folder.most_common(10)),
    }


def short(text: str, limit: int = 100) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def markdown(facts: dict[str, Any]) -> str:
    """The hub's Repository block: facts only, rewritten whole on each refresh."""
    scanned = f"- **Scanned:** commit `{facts['commit']}`"
    if facts["commit_date"]:
        scanned += f" of {facts['commit_date']}"
    if facts["branch"]:
        scanned += f" on `{facts['branch']}`"
    if origin := facts["origin"]:
        scanned += f", origin <{origin}>" if "://" in origin else f", origin `{origin}`"
    lines = [scanned]
    kinds = " · ".join(f"`{ext}` {n}" for ext, n in facts["extensions"].items())
    lines.append(f"- **Files:** {facts['files']} tracked" + (f"; {kinds}" if kinds else ""))
    if facts["manifests"]:
        lines.append("- **Manifests:**")
        for m in facts["manifests"][:10]:
            about = [str(m[k]) for k in ("name", "version") if m.get(k)]
            if m.get("requires_python"):
                about.append(f"Python {m['requires_python']}")
            if m.get("go"):
                about.append(f"Go {m['go']}")
            if deps := m.get("dependencies"):
                about.append(f"{len(deps)} dependencies: {', '.join(deps[:8])}" + (", …" if len(deps) > 8 else ""))
            lines.append(f"  - `{m['path']}`" + (f": {'; '.join(about)}" if about else ""))
        if len(facts["manifests"]) > 10:
            lines.append(f"  - and {len(facts['manifests']) - 10} more")
    if facts["layout"]:
        lines.append("- **Layout:**")
        for item in facts["layout"]:
            inner = ", ".join(f"`{c['folder']}/` {c['files']}" for c in item["children"])
            files = f"{item['files']} file" + ("s" if item["files"] != 1 else "")
            lines.append(f"  - `{item['folder']}/` {files}" + (f": {inner}" if inner else ""))
    docs = []
    if facts["readme"]:
        title = facts["readme"]["title"]
        docs.append(f"`{facts['readme']['path']}`" + (f' "{short(title, 60)}"' if title else ""))
    for d in facts["docs"]:
        docs.append(f"`{d['path']}` ({d['markdown']} Markdown)" if d["exists"] else f"`{d['path']}` (missing)")
    if docs:
        lines.append(f"- **Docs:** {' · '.join(docs)}")
    if facts["ci"]:
        lines.append(f"- **CI:** {' · '.join(f'`{f}`' for f in facts['ci'])}")
    if facts["recent"]:
        lines.append("- **Recent commits:**")
        lines += [f"  - {c['date']} `{c['sha']}` {short(c['subject'])}" for c in facts["recent"][:5]]
    return "\n".join(lines) + "\n"


# --- decision numbers ---------------------------------------------------------


def link_title(value: object) -> str:
    """The note a `[[link]]` points to (`[[Folder/Name#h|alias]]` → `Name`), or the plain text."""
    text = str(value or "").strip()
    match = LINK.match(text)
    return (match.group(1) if match else text).rsplit("/", 1)[-1].strip()


def decision_number(query: dict[str, Any], project: str) -> dict[str, Any]:
    wanted = project.casefold()
    numbers = [
        n["number"]
        for n in query.get("notes") or []
        if n.get("type") == "decision"
        and link_title(n.get("project")).casefold() == wanted
        and isinstance(n.get("number"), int)
        and not isinstance(n.get("number"), bool)
    ]
    return {"ok": True, "project": project, "number": max(numbers, default=0) + 1, "numbered": len(numbers)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan", help="read-only facts about a repository")
    sc.add_argument("--repo", required=True, help="local path of the repository (the hub's `repo`)")
    sc.add_argument("--docs", action="append", default=[], help="a docs path, relative to the repository or absolute")
    sc.add_argument("--last", "--since", dest="last",
                    help="the hub's `scanned_commit`: what changed since, and whether this clone is newer")  # fmt: skip
    sc.add_argument("--branch", help="the hub's `branch`: report when another one is checked out")
    sc.add_argument("--markdown", action="store_true", help="print the hub's Repository block instead of JSON")
    dn = sub.add_parser(
        "decision-number", help="next decision number of a project, from `synapsidian query` JSON on stdin"
    )
    dn.add_argument("--project", required=True, help="the project's hub title")
    args = parser.parse_args()

    if args.cmd == "decision-number":
        try:
            query = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError as exc:
            fail(2, f"stdin is not `synapsidian query notes` JSON: {exc}")
        print(json.dumps(decision_number(query, args.project), ensure_ascii=False))
        return

    if is_url(args.repo):
        fail(2, f"{args.repo} is a URL; scan needs a local clone (`synapsidian-projects repo resolve` finds it)")
    repo = Path(args.repo).expanduser()
    if not repo.is_dir():
        fail(2, f"{repo} is not a folder")
    if git(repo, "rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
        fail(2, f"{repo} is not in a git repository")
    facts = scan(repo.resolve(), args.docs, args.last, args.branch)
    if args.markdown:
        sys.stdout.write(markdown(facts))
    else:
        print(json.dumps(facts, ensure_ascii=False))


if __name__ == "__main__":
    main()
