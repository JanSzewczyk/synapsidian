"""A project's repository across devices: URL or local path, resolved per vault clone (D139-D141)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECTS
from synapsidianlib import schema, vault

SCRIPTS = PROJECTS / "scripts"
URL = "https://github.com/Org/Web-App"


def tool(script: str, *args: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), *args], capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(repo: Path, rel: str, message: str) -> str:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(message + "\n")
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def clone_of(root: Path, *remotes: tuple[str, str]) -> Path:
    """A repository with an app folder and the given remotes."""
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    commit(root, "apps/web/src/main.ts", "first")
    for name, url in remotes:
        git(root, "remote", "add", name, url)
    return root


@pytest.fixture
def repos(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import repos as module

    return module


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ("https://github.com/Org/Web-App", URL),
        ("https://github.com/Org/Web-App.git", URL),
        ("https://user:s3cr3t@GitHub.com/Org/Web-App/", URL),
        ("git@github.com:Org/Web-App.git", URL),
        ("ssh://git@github.com:22/Org/Web-App.git", URL),
        ("git+ssh://git@github.com/Org/Web-App", URL),
        ("github.com:Org/Web-App.git", URL),
        ("https://gitlab.example.com/group/sub/app.git", "https://gitlab.example.com/group/sub/app"),
        ("/Users/someone/code/web-app", None),
        ("file:///Users/someone/code/web-app", None),
        ("C:/code/web-app", None),
        ("https://github.com/", None),
    ],
)
def test_every_spelling_of_a_remote_has_one_canonical_url(repos, remote, expected):
    assert repos.canonical(remote) == expected
    assert repos.key_of(remote) == (expected.removeprefix("https://").casefold() if expected else None)


def test_a_url_is_resolved_per_device_and_a_wrong_folder_is_never_bound(tmp_path):
    state = tmp_path / "vault/.git/synapsidian"
    a = clone_of(tmp_path / "laptop/web-app", ("origin", "git@github.com:org/web-app.git"))
    base = ("--state", str(state), "--repo", URL)

    code, out = tool("repos", "resolve", *base)
    assert code == 0 and out["how"] == "missing" and out["key"] == "github.com/org/web-app"
    assert not (state / "synapsidian-projects/repos.json").exists()  # asking binds nothing

    # A session started inside the clone (in the app's folder) binds it: no question needed.
    code, out = tool("repos", "resolve", *base, "--path", "apps/web", "--cwd", str(a / "apps/web/src"))
    assert code == 0 and out["how"] == "cwd" and out["bound"] is True
    assert Path(out["clone"]).resolve() == a.resolve() and Path(out["dir"]).resolve() == (a / "apps/web").resolve()
    code, out = tool("repos", "resolve", *base)
    assert out["how"] == "map" and Path(out["dir"]).resolve() == a.resolve()
    assert tool("repos", "resolve", *base, "--path", "../outside")[0] == 2

    # Another repository's folder is never bound, and its credentials never printed.
    other = clone_of(tmp_path / "other", ("origin", "https://bot:tok3n@github.com/org/other.git"))
    code, out = tool("repos", "bind", *base, "--clone", str(other))
    assert code == 2 and out["remotes"] == {"origin": "https://github.com/org/other"} and "tok3n" not in json.dumps(out)
    # A fork's clone names the repository as `upstream`, which counts.
    fork = clone_of(tmp_path / "fork", ("origin", "git@github.com:me/web-app.git"), ("upstream", URL + ".git"))
    code, out = tool("repos", "bind", *base, "--clone", str(fork))
    assert code == 0 and Path(out["clone"]).resolve() == fork.resolve()

    # The bound folder now points elsewhere: say so, with its remotes.
    git(fork, "remote", "remove", "upstream")
    code, out = tool("repos", "resolve", *base)
    assert out["how"] == "mismatch" and out["remotes"] == {"origin": "https://github.com/me/web-app"}
    # Moved away: ask again, naming the old folder.
    shutil.move(fork, tmp_path / "moved")
    code, out = tool("repos", "resolve", *base)
    assert out["how"] == "missing" and Path(out["stale"]).name == "fork"

    _, listed = tool("repos", "list", "--state", str(state))
    assert [(r["key"], r["status"]) for r in listed["repos"]] == [("github.com/org/web-app", "missing")]
    assert tool("repos", "forget", *base)[1]["removed"] is True
    assert tool("repos", "list", "--state", str(state))[1]["repos"] == []
    assert tool("repos", "bind", "--state", str(state), "--repo", str(a), "--clone", str(a))[0] == 2  # not a URL
    assert tool("repos", "resolve", "--state", "relative/state", "--repo", URL)[0] == 2


def test_a_local_path_stays_the_users_choice_and_is_not_an_error_on_another_device(tmp_path):
    state = tmp_path / "state"
    repo = clone_of(tmp_path / "web-app", ("origin", "https://github.com/org/web-app.git"))
    code, out = tool("repos", "resolve", "--state", str(state), "--repo", str(repo / "apps/web"))
    assert code == 0 and out["how"] == "local" and out["path_in_repo"] == "apps/web"
    assert out["origin"] == "https://github.com/org/web-app" and Path(out["toplevel"]).resolve() == repo.resolve()

    unpushed = clone_of(tmp_path / "notes-tool")
    _, out = tool("repos", "resolve", "--state", str(state), "--repo", str(unpushed))
    assert out["how"] == "local" and out["origin"] is None and out["path_in_repo"] is None

    _, out = tool("repos", "resolve", "--state", str(state), "--repo", "/Users/someone-else/code/web-app")
    assert out["how"] == "elsewhere" and out["dir"] is None

    assert tool("repos", "keep-path", "--state", str(state), "--title", "Web app")[1]["keep_path"] == ["Web app"]
    assert tool("repos", "list", "--state", str(state))[1]["keep_path"] == ["Web app"]


def test_a_scan_never_writes_facts_older_than_the_last_ones(tmp_path):
    """Two clones fetched at different times: only the newer one may write (D141)."""
    upstream = clone_of(tmp_path / "upstream")
    c1 = git(upstream, "rev-parse", "HEAD")
    other = tmp_path / "other-device"
    git(tmp_path, "clone", "-q", str(upstream), str(other))
    c2 = commit(upstream, "apps/web/src/chart.ts", "feat: chart")

    def scan(repo: Path, *args: str) -> dict:
        code, out = tool("projects", "scan", "--repo", str(repo), *args)
        assert code == 0, out
        return out

    assert {k: scan(upstream)[k] for k in ("freshness", "write")} == {"freshness": "first", "write": True}
    ahead = scan(upstream, "--last", c1[:7])
    assert (ahead["freshness"], ahead["write"], ahead["distance"], ahead["since"]["count"]) == ("ahead", True, 1, 1)
    assert scan(upstream, "--since", c2)["freshness"] == "same"  # the old option name still works

    # The other device hasn't fetched the commit the hub was scanned at.
    unknown = scan(other, "--last", c2)
    assert (unknown["freshness"], unknown["write"]) == ("unknown", False)
    git(other, "fetch", "-q")  # the user's own fetch, not the plugin's
    behind = scan(other, "--last", c2)
    assert (behind["freshness"], behind["write"], behind["distance"]) == ("behind", False, 1)
    commit(other, "apps/web/src/other.ts", "wip on the other device")
    assert scan(other, "--last", c2)["freshness"] == "diverged"

    off = scan(upstream, "--last", c2, "--branch", "release")
    assert off["write"] is False and off["off_branch"] == {"expected": "release", "current": "main"}

    code, app = tool("architect", "scan", "--repo", str(other), "--app", "apps/web", "--last", c2)
    assert code == 0 and (app["freshness"], app["write"]) == ("diverged", False)


def test_where_names_the_untracked_state_folder_and_hubs_take_path_and_branch(run, projects_vault):
    code, where = run("note", "where", vault=projects_vault)
    assert code == 0 and Path(where["state"]) == projects_vault / ".git" / "synapsidian"
    code, hub = run("note", "new", "--type", "project", "--title", "Web app", "--field", "summary=s",
                    "--field", "kind=repository", "--field", f"repo={URL}", "--field", "path=apps/web",
                    "--field", "branch=main", vault=projects_vault)  # fmt: skip
    assert code == 0, hub
    s = schema.load(projects_vault)
    note = next(n for n in vault.iter_notes(projects_vault) if n.rel == hub["rel"])
    assert schema.validate(note.meta, note.rel, s) == []
