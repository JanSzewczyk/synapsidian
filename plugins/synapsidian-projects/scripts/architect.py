#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only architecture scan of one app in a repository, for /synapsidian-projects:architect (D81, D109).

  architect.py apps --repo PATH
  architect.py scan --repo PATH --app REL [--last COMMIT] [--branch NAME]

PATH is the project hub's `repo`: a local clone, or a folder inside one. `apps` lists what can
be scanned there: PATH itself when it has a manifest, and every folder up to two levels down
with one (`apps/web`, `packages/api`), each with its name, its path and its profile.

`scan` describes the app at REL ("." for PATH itself). For any language: its manifests (name,
version, dependencies), top-level folders, the source root (`src/`, `lib/`, `app/`, `internal/`,
`pkg/`, or the Python package) and its modules with file and line counts, entry points, and
the largest code files. The `vue` profile, for an app whose package.json depends on Vue, also
reads `src/domains/*` as its modules, with the Pinia stores they define and the domains they
import, plus the router's routes. With --last (the notes' `scanned_commit`; --since is the old
name), the files changed since that commit, grouped by module. `freshness`, `write`,
`distance` and `off_branch` are `projects.py scan`'s (D141): with `write: false` this clone is
not newer than the notes. `path` is the app's folder from the repository root, the note field
of that name.

Only tracked files are read, with the same read-only git commands as `projects.py scan`.
The model writes the notes; this script writes nothing anywhere.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from projects import MANIFEST_SUFFIXES, MANIFESTS, SKIP_PARTS, fail, freshness, git, is_url, manifest_facts

CODE_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".java", ".kt", ".kts",
    ".scala", ".rb", ".php", ".cs", ".fs", ".swift", ".m", ".mm", ".c", ".h", ".cc", ".cpp", ".hpp", ".ex", ".exs",
    ".erl", ".clj", ".dart", ".lua", ".sh", ".sql",
}  # fmt: skip
# Tests and stories (`.spec.ts`, `test_x.py`, `x_test.go`, `__tests__/`) aren't app code.
TEST = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(spec|test|stories|story)\.|(^|/)test_[^/]*\.py$|_test\.(go|py)$")
SOURCE_ROOTS = ("src", "lib", "app", "internal", "pkg", "packages")
ENTRY_NAMES = re.compile(
    r"(^|/)(main\.(py|ts|js|go|rs|kt|java|swift|c|cpp)|index\.(ts|js|tsx|jsx)|app\.(py|ts|js)|__main__\.py"
    r"|manage\.py|server\.(ts|js|py|go)|cli\.(py|ts|js))$|(^|/)bin/[^/]+$"
)
VUE_DOMAIN_IMPORT = re.compile(r"""from\s+['"]@/domains/([A-Za-z0-9_-]+)""")
VUE_STORE_ID = re.compile(r"""defineStore\(\s*['"]([^'"]+)['"]""")
ROUTE_PATH = re.compile(r"""\bpath:\s*['"`]([^'"`]*)['"`]""")
ROUTE_NAME = re.compile(r"""\bname:\s*['"`]([^'"`]+)['"`]""")
ROUTE_COMPONENT = re.compile(r"""\bcomponent:\s*(?:\(\)\s*=>\s*import\(\s*['"]([^'"]+)['"]\s*\)|([A-Za-z_$][\w$]*))""")
KEY_DEPENDENCIES = (
    "vue", "vue-router", "pinia", "vuex", "@tanstack/vue-query", "vue-i18n", "axios", "zod", "@vueuse/core",
    "chart.js", "echarts", "highcharts", "d3", "primevue", "vuetify", "element-plus", "tailwindcss", "less", "sass",
)  # fmt: skip
VUE_TOOLING = ("vite", "vitest", "@playwright/test", "storybook", "eslint", "oxlint", "typescript", "knip", "msw")


def tracked(app_dir: Path) -> list[str]:
    """Tracked files under the app, relative to it, without vendored or generated trees."""
    files = [f for f in git(app_dir, "ls-files", "-z").split("\0") if f]
    return [f for f in files if not SKIP_PARTS.intersection(f.split("/")[:-1])]


def is_manifest(name: str) -> bool:
    return name in MANIFESTS or name.endswith(MANIFEST_SUFFIXES)


def line_count(path: Path) -> int:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def package_json(app_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((app_dir / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def profile_of(app_dir: Path) -> str:
    data = package_json(app_dir)
    return "vue" if "vue" in {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})} else "generic"


# --- apps ---------------------------------------------------------------------


def apps(repo: Path) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for f in tracked(repo):
        parts = f.split("/")
        if len(parts) <= 3 and is_manifest(parts[-1]):
            rel = "/".join(parts[:-1]) or "."
            if rel not in found:
                app_dir = repo / rel
                name = app_dir.resolve().name
                found[rel] = {"app": name, "path": rel, "manifest": parts[-1], "profile": profile_of(app_dir)}
    return sorted(found.values(), key=lambda a: (a["path"] != ".", a["path"]))


# --- scan ---------------------------------------------------------------------


def source_root(app_dir: Path, code: list[str], profile: str) -> str:
    """The folder that holds the app's own modules, or "." when the code sits at the top."""
    if profile == "vue":
        return "src"
    tops = Counter(f.split("/", 1)[0] for f in code if "/" in f)
    for name in SOURCE_ROOTS:
        if tops.get(name):
            return name
    pyproject = app_dir / "pyproject.toml"
    project = manifest_facts(pyproject).get("name") if pyproject.is_file() else None
    package = re.sub(r"[-.]", "_", str(project or "")).lower()
    if package and tops.get(package):
        return package
    return "."


def under(files: list[str], folder: str) -> list[str]:
    return files if folder == "." else [f[len(folder) + 1 :] for f in files if f.startswith(folder + "/")]


def module_of(path: str, root: str) -> str | None:
    inner = path if root == "." else (path[len(root) + 1 :] if path.startswith(root + "/") else None)
    if inner is None or "/" not in inner:
        return None
    return inner.split("/", 1)[0]


def entry_points(app_dir: Path, files: list[str]) -> list[str]:
    found = [f for f in files if ENTRY_NAMES.search(f) and not TEST.search(f) and f.count("/") <= 3]
    data = package_json(app_dir)
    for key in ("main", "module"):
        if isinstance(data.get(key), str):
            found.append(f"package.json {key}: {data[key]}")
    bins = data.get("bin")
    if isinstance(bins, dict):
        found += [f"package.json bin {name}: {target}" for name, target in sorted(bins.items())]
    if (app_dir / "pyproject.toml").is_file():
        scripts = manifest_facts(app_dir / "pyproject.toml").get("scripts") or []
        found += [f"pyproject script: {name}" for name in scripts]
    return sorted(dict.fromkeys(found), key=lambda f: (f.count("/"), f))[:20]


def vue_domains(app_dir: Path, code: list[str]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Modules, store ids and routes of a Vue app organised in `src/domains/<name>/`."""
    texts = {f: read(app_dir / f) for f in code if f.startswith("src/")}
    domains: dict[str, dict[str, Any]] = {}
    for f, text in texts.items():
        match = re.match(r"src/domains/([^/]+)/", f)
        if not match:
            continue
        d = domains.setdefault(match.group(1), {"imports": Counter(), "stores": set()})
        d["imports"].update(x for x in VUE_DOMAIN_IMPORT.findall(text) if x != match.group(1))
        d["stores"].update(VUE_STORE_ID.findall(text))
    stores = sorted({s for text in texts.values() for s in VUE_STORE_ID.findall(text)})
    routes: list[dict[str, Any]] = []
    for f, text in texts.items():
        if not f.startswith("src/router/"):
            continue
        starts = [m.start() for m in ROUTE_PATH.finditer(text)]
        for i, start in enumerate(starts):
            chunk = text[start : starts[i + 1] if i + 1 < len(starts) else start + 600]
            name, component = ROUTE_NAME.search(chunk), ROUTE_COMPONENT.search(chunk)
            routes.append({
                "path": ROUTE_PATH.match(text, start).group(1),  # type: ignore[union-attr]
                "name": name.group(1) if name else None,
                "component": (component.group(1) or component.group(2)) if component else None,
                "file": f.removeprefix("src/"),
            })  # fmt: skip
    extra = [{"name": n, "stores": sorted(d["stores"]), "depends_on": dict(d["imports"].most_common())}
             for n, d in sorted(domains.items())]  # fmt: skip
    return extra, stores, routes


def scan(app_dir: Path, since: str | None, branch: str | None = None) -> dict[str, Any]:
    files = tracked(app_dir)
    if not files:
        fail(2, f"{app_dir} holds no tracked files")
    profile = profile_of(app_dir)
    all_code = [f for f in files if Path(f).suffix.lower() in CODE_SUFFIXES]
    code = [f for f in all_code if not TEST.search(f)]
    tests = [f for f in all_code if TEST.search(f)]
    lines = {f: line_count(app_dir / f) for f in code}
    root = "src/domains" if profile == "vue" and any(f.startswith("src/domains/") for f in code) else None
    root = root or source_root(app_dir, code, profile)
    for _ in range(3):  # all the code in one folder (`plugins/`): its subfolders are the modules
        inside = {module_of(f, root) for f in code}
        if len(inside) != 1 or None in inside:
            break
        root = inside.pop() if root == "." else f"{root}/{inside.pop()}"

    folders: dict[str, list[str]] = defaultdict(list)
    for f in code:
        folders[f.split("/", 1)[0] if "/" in f else "(root)"].append(f)
    modules: dict[str, dict[str, Any]] = {}
    for f in code:
        if (name := module_of(f, root)) is not None:
            m = modules.setdefault(name, {"name": name, "files": 0, "test_files": 0, "lines": 0})
            m["files"] += 1
            m["lines"] += lines[f]
    for f in tests:
        if (name := module_of(f, root)) in modules:
            modules[name]["test_files"] += 1
    for m in modules.values():
        folder = app_dir / (m["name"] if root == "." else f"{root}/{m['name']}")
        m["subdirs"] = sorted(d.name for d in folder.iterdir() if d.is_dir()) if folder.is_dir() else []

    result: dict[str, Any] = {
        "ok": True,
        "app": app_dir.resolve().name,
        "path": git(app_dir, "rev-parse", "--show-prefix").strip().rstrip("/") or ".",
        "repo": git(app_dir, "rev-parse", "--show-toplevel").strip(),
        "commit": git(app_dir, "rev-parse", "HEAD").strip(),
        "commit_date": git(app_dir, "log", "-1", "--format=%cs").strip(),
        "profile": profile,
        "manifests": [{"path": f, **manifest_facts(app_dir / f)} for f in files if "/" not in f and is_manifest(f)],
        "folders": [
            {"folder": n, "files": len(fs), "lines": sum(lines[f] for f in fs)}
            for n, fs in sorted(folders.items(), key=lambda item: -len(item[1]))
        ][:15],
        "source_root": root,
        "modules": sorted(modules.values(), key=lambda m: -m["files"]),
        "entry_points": entry_points(app_dir, files),
        "test_files": len(tests),
        "largest": [{"file": f, "lines": n} for f, n in sorted(lines.items(), key=lambda item: -item[1])[:10]],
        **freshness(app_dir, since, branch),
    }
    if profile == "vue":
        data = package_json(app_dir)
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        result["package"] = {
            "name": data.get("name"),
            "dependencies": {k: deps[k] for k in KEY_DEPENDENCIES if k in deps},
            "tooling": {k: deps[k] for k in deps if k in VUE_TOOLING or k == "@storybook/vue3-vite"},
            "scripts": sorted(data.get("scripts") or {}),
        }
        extra, result["stores"], result["routes"] = vue_domains(app_dir, code)
        by_name = {e["name"]: e for e in extra}
        used_by = Counter(d for e in extra for d in e["depends_on"])
        for m in result["modules"]:
            m |= {k: v for k, v in by_name.get(m["name"], {}).items() if k != "name"}
            m["used_by_modules"] = used_by.get(m["name"], 0)
    if since:
        result["changed"] = changes(app_dir, since, root)
    return result


def changes(app_dir: Path, since: str, root: str) -> dict[str, Any]:
    if not git(app_dir, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}", check=False).strip():
        return {"since": since, "known": False}
    changed = [f for f in git(app_dir, "diff", "--name-only", "--relative", since, "HEAD", "--", ".").splitlines() if f]
    by_module: dict[str, list[str]] = defaultdict(list)
    for f in changed:
        by_module[module_of(f, root) or "(outside modules)"].append(f)
    return {"since": since, "known": True, "files": len(changed), "by_module": dict(by_module)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ap = sub.add_parser("apps", help="what can be scanned in the repository")
    ap.add_argument("--repo", required=True, help="the project hub's `repo`: a local path")
    sc = sub.add_parser("scan", help="read-only facts about one app")
    sc.add_argument("--repo", required=True, help="the project hub's `repo`: a local path")
    sc.add_argument("--app", required=True, help='the app\'s path from `apps` ("." for the repository itself)')
    sc.add_argument("--last", "--since", dest="last", help="commit of the previous scan (the notes' `scanned_commit`)")
    sc.add_argument("--branch", help="the hub's `branch`: report when another one is checked out")
    args = parser.parse_args()

    if is_url(args.repo):
        fail(
            2, f"{args.repo} is a URL; the architect reads a local clone (`synapsidian-projects repo resolve` finds it)"
        )
    repo = Path(args.repo).expanduser()
    if not repo.is_dir() or git(repo, "rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
        fail(2, f"{repo} is not a folder in a git repository; fix the hub's `repo`")
    if args.cmd == "apps":
        print(json.dumps({"ok": True, "repo": str(repo), "apps": apps(repo)}, ensure_ascii=False))
        return
    app_dir = (repo / args.app).resolve()
    if not app_dir.is_dir() or not app_dir.is_relative_to(repo.resolve()):
        fail(2, f"no app {args.app!r} in {repo}; `apps` lists them")
    print(json.dumps(scan(app_dir, args.last, args.branch), ensure_ascii=False))


if __name__ == "__main__":
    main()
