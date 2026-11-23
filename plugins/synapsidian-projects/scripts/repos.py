#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Where a project's repository is on this device (D139, D140).

  repos.py resolve --state DIR --repo REPO [--path REL] [--cwd DIR]
  repos.py bind --state DIR --repo URL --clone DIR
  repos.py forget --state DIR --repo URL
  repos.py keep-path --state DIR --title TITLE
  repos.py list --state DIR

REPO is the hub's `repo`: a remote URL, the same on every device, or an absolute local path,
which ties the project to one device. DIR for --state is what `synapsidian note where` prints as
`state`; the map of URLs to clones lives in `<state>/synapsidian-projects/repos.json`, which git never
tracks, so each device keeps its own.

`resolve` prints {ok, how, key, clone, dir}. `how`:
  local      the hub holds a path and it is a git work tree here
  elsewhere  the hub holds a path that isn't here: the project is read on another device
  map        a URL whose clone this device has bound
  cwd        a URL whose clone is the folder given with --cwd; it is bound now (`bound`)
  missing    a URL with no clone known on this device
  mismatch   the bound folder's remotes no longer name the URL (`remotes` lists them)
`dir` is the folder to scan: the clone, or the hub's `path` inside it. For `local`, `origin`
is the clone's remote URL in canonical form (or null) and `path_in_repo` the folder from the
repository root, which is what a switch to the URL form needs.

`bind` records a clone for a URL after checking that one of its remotes names it; `forget`
removes the record. `keep-path` remembers that the user keeps a hub's local path, so setup
doesn't offer the switch again on this device. `list` prints the map with each clone's state.

Only `git rev-parse` and `git remote -v` run in a clone, read-only and with its exec keys off
(D120). Exit 2 = bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from projects import fail, git, is_url

MAP_VERSION = 1
SCP = re.compile(r"^(?:[^@/\s]+@)?(?P<host>[^:/\s]+):(?P<path>(?!//).+)$")  # git@host:owner/name.git
URL_SCHEMES = {"https", "http", "ssh", "git", "git+ssh", "ssh+git"}


def canonical(remote: str) -> str | None:
    """`https://<host>/<path>` for a remote URL, without credentials, port, `.git` or slashes.

    None for what has no host: a local path or a `file://` remote.
    """
    remote = remote.strip()
    parts = urlsplit(remote)
    if parts.scheme.lower() in URL_SCHEMES and parts.hostname:
        host, path = parts.hostname, parts.path
    elif len(parts.scheme) != 1 and (match := SCP.match(remote)):  # `C:/repo` is a Windows path
        host, path = match["host"], match["path"]
    else:
        return None
    path = path.strip("/").removesuffix(".git").strip("/")
    return f"https://{host.lower()}/{path}" if path else None


def key_of(url: str) -> str | None:
    """The map's key: the canonical URL without its scheme, case-folded (`github.com/o/r`)."""
    url = canonical(url) or ""
    return url.removeprefix("https://").casefold() or None


# --- clones -------------------------------------------------------------------


def toplevel(folder: Path) -> Path | None:
    """The work tree holding `folder`, or None when it isn't in one."""
    if not folder.is_dir():
        return None
    if git(folder, "rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
        return None
    top = git(folder, "rev-parse", "--show-toplevel", check=False).strip()
    return Path(top) if top else None


def remotes(clone: Path) -> dict[str, str]:
    """Each remote's fetch URL, by name, after git's own `insteadOf` rewrites."""
    found: dict[str, str] = {}
    for line in git(clone, "remote", "-v", check=False).splitlines():
        name, _, rest = line.partition("\t")
        url, _, kind = rest.rpartition(" ")
        if kind == "(fetch)" and name and url:
            found[name] = url
    return found


def names(clone: Path, key: str) -> bool:
    """Whether any remote of the clone is the repository `key` (a fork's `upstream` counts)."""
    return any(key_of(url) == key for url in remotes(clone).values())


def public_remotes(clone: Path) -> dict[str, str | None]:
    return {name: canonical(url) for name, url in remotes(clone).items()}


# --- the map ------------------------------------------------------------------


def map_file(state: Path) -> Path:
    return state / "synapsidian-projects" / "repos.json"


def load(state: Path) -> dict[str, Any]:
    try:
        data = json.loads(map_file(state).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    except (OSError, ValueError) as exc:
        fail(2, f"{map_file(state)} is unreadable ({exc}); fix or delete it")
    if not isinstance(data, dict):
        fail(2, f"{map_file(state)} is not a JSON object; fix or delete it")
    return {
        "version": MAP_VERSION,
        "repos": dict(data.get("repos") or {}),
        "keep_path": list(data.get("keep_path") or []),
    }


def save(state: Path, data: dict[str, Any]) -> None:
    """Write the map whole, through a temporary file, so a crash never leaves half of it."""
    path = map_file(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.write("\n")
    Path(tmp.name).replace(path)


def state_dir(raw: str) -> Path:
    state = Path(raw).expanduser()
    if not raw.strip() or not state.is_absolute():
        fail(2, "--state needs the absolute `state` folder that `synapsidian note where` prints")
    return state


def url_key(repo: str) -> str:
    key = key_of(repo) if is_url(repo) else None
    if key is None:
        fail(2, f"{repo!r} is not a repository URL (https://host/owner/name or git@host:owner/name)")
    return key


# --- commands -----------------------------------------------------------------


def with_dir(result: dict[str, Any], base: Path, path: str | None) -> dict[str, Any]:
    """Add the folder to scan, `<base>/<path>`, refusing a path that leaves the repository."""
    target = (base / path).resolve() if path and path.strip(" ./") else base
    if not target.is_relative_to(base.resolve()) or not target.is_dir():
        fail(2, f"no folder {path!r} in {base}; fix the hub's `path`")
    return {**result, "dir": str(target)}


def resolve(state: Path, repo: str, path: str | None, cwd: str | None) -> dict[str, Any]:
    if not is_url(repo):
        given = Path(repo).expanduser()
        top = toplevel(given) if given.is_absolute() else None
        if top is None:
            return {"ok": True, "how": "elsewhere", "key": None, "clone": None, "dir": None, "repo": repo}
        origin = remotes(top).get("origin")
        inside = given.resolve().relative_to(top.resolve()).as_posix()
        result = {"ok": True, "how": "local", "key": None, "clone": str(given), "repo": repo,
                  "toplevel": str(top), "origin": canonical(origin) if origin else None,
                  "path_in_repo": inside if inside != "." else None}  # fmt: skip
        return with_dir(result, given, path)

    key = url_key(repo)
    data = load(state)
    base = {"ok": True, "key": key, "url": canonical(repo)}
    entry = data["repos"].get(key) or {}
    stale = None
    if clone := entry.get("path"):
        top = toplevel(Path(clone))
        if top is not None and names(top, key):
            return with_dir({**base, "how": "map", "clone": str(top)}, top, path)
        if top is not None:
            return {**base, "how": "mismatch", "clone": str(top), "dir": None, "remotes": public_remotes(top)}
        stale = clone  # bound once, gone now: try the session's folder, else ask again

    if cwd and (top := toplevel(Path(cwd).expanduser())) is not None and names(top, key):
        data["repos"][key] = {"path": str(top), "bound": date.today().isoformat()}
        save(state, data)
        return with_dir({**base, "how": "cwd", "clone": str(top), "bound": True}, top, path)
    return {**base, "how": "missing", "clone": None, "dir": None, "stale": stale}


def bind(state: Path, repo: str, clone: str) -> dict[str, Any]:
    key = url_key(repo)
    top = toplevel(Path(clone).expanduser())
    if top is None:
        fail(2, f"{clone} is not a folder in a git repository")
    if not names(top, key):
        print(json.dumps({"ok": False, "error": f"no remote of {top} is {canonical(repo)}",
                          "remotes": public_remotes(top)}))  # fmt: skip
        raise SystemExit(2)
    data = load(state)
    data["repos"][key] = {"path": str(top), "bound": date.today().isoformat()}
    save(state, data)
    return {"ok": True, "key": key, "url": canonical(repo), "clone": str(top)}


def forget(state: Path, repo: str) -> dict[str, Any]:
    key = url_key(repo)
    data = load(state)
    removed = data["repos"].pop(key, None)
    if removed is not None:
        save(state, data)
    return {"ok": True, "key": key, "removed": removed is not None}


def keep_path(state: Path, title: str) -> dict[str, Any]:
    if not title.strip():
        fail(2, "--title needs the hub's title")
    data = load(state)
    if title not in data["keep_path"]:
        data["keep_path"] = sorted({*data["keep_path"], title})
        save(state, data)
    return {"ok": True, "keep_path": data["keep_path"]}


def listing(state: Path) -> dict[str, Any]:
    data = load(state)
    repos = []
    for key, entry in sorted(data["repos"].items()):
        top = toplevel(Path(entry.get("path") or "/nonexistent"))
        status = "missing" if top is None else ("ok" if names(top, key) else "mismatch")
        repos.append({"key": key, "url": f"https://{key}", **entry, "status": status})
    return {"ok": True, "file": str(map_file(state)), "repos": repos, "keep_path": data["keep_path"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    state_help = "the `state` folder `synapsidian note where` prints"
    rs = sub.add_parser("resolve", help="the clone of a hub's `repo` on this device")
    rs.add_argument("--state", required=True, help=state_help)
    rs.add_argument("--repo", required=True, help="the hub's `repo`: a remote URL or a local path")
    rs.add_argument("--path", help="the hub's `path`: a folder inside the repository")
    rs.add_argument("--cwd", help="the session's folder, bound when it is a clone of the URL")
    bd = sub.add_parser("bind", help="record this device's clone of a repository URL")
    bd.add_argument("--state", required=True, help=state_help)
    bd.add_argument("--repo", required=True, help="the repository URL")
    bd.add_argument("--clone", required=True, help="the local clone (any folder inside it)")
    fg = sub.add_parser("forget", help="drop this device's clone of a repository URL")
    fg.add_argument("--state", required=True, help=state_help)
    fg.add_argument("--repo", required=True, help="the repository URL")
    kp = sub.add_parser("keep-path", help="remember that a hub keeps its local path on this device")
    kp.add_argument("--state", required=True, help=state_help)
    kp.add_argument("--title", required=True, help="the hub's title")
    ls = sub.add_parser("list", help="this device's clones")
    ls.add_argument("--state", required=True, help=state_help)
    args = parser.parse_args()

    state = state_dir(args.state)
    match args.cmd:
        case "resolve":
            result = resolve(state, args.repo, args.path, args.cwd)
        case "bind":
            result = bind(state, args.repo, args.clone)
        case "forget":
            result = forget(state, args.repo)
        case "keep-path":
            result = keep_path(state, args.title)
        case _:
            result = listing(state)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
