from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from conftest import PROJECTS, WORK
from synapsidianlib import frontmatter, schema, vault

BIN = PROJECTS / "bin" / "synapsidian-projects"
HEADING = re.compile(r"^## .+$", re.MULTILINE)

OLD_TASKS_BASE = """filters:
  and:
    - file.inFolder("Tasks")
    - note.type == "task"
views:
  - type: table
    name: Mine
    filters:
      and:
        - file.inFolder("Tasks")
"""
OLD_INBOX_BASE = 'filters:\n  and:\n    - file.inFolder("Inbox")\nviews:\n  - type: table\n    name: To triage\n'
USER_BASE = 'filters:\n  and:\n    - file.inFolder("Reading")\n    - note.type == "note"\nviews: []\n'


def bin_run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(BIN), *args], capture_output=True, text=True)


def test_installing_files_project_notes_under_the_project_and_switches_old_bases(run, tmp_path):
    root = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(root), "--name", "N", "--email", "e@x")
    run("setup", "extension", "--vault", str(root), "--from", str(WORK / "extension"))
    # A vault set up before 0.18.0: its Bases still pick types by folder.
    (root / "Bases/Tasks.base").write_text(OLD_TASKS_BASE)
    (root / "Bases/Inbox.base").write_text(OLD_INBOX_BASE)
    (root / "Bases/Reading.base").write_text(USER_BASE)

    code, out = run("setup", "extension", "--vault", str(root), "--from", str(PROJECTS / "extension"))

    assert code == 0 and out["commit"] and out["extension"] == "synapsidian-projects", out
    assert {"Bases/Tasks.base", "Bases/Inbox.base"} <= set(out["updated"])
    tasks_base = (root / "Bases/Tasks.base").read_text()
    new_filter = '    - not:\n        - file.inFolder("Archive")\n    - note.type == "task"\n'
    assert tasks_base.startswith("filters:\n  and:\n" + new_filter)
    assert tasks_base.count('file.inFolder("Tasks")') == 1  # a view's own filter is the user's
    assert '- note.type == "capture"' in (root / "Bases/Inbox.base").read_text()  # the type it lacked
    assert (root / "Bases/Reading.base").read_text() == USER_BASE  # not a type folder: untouched

    new = ("note", "new", "--field", "summary=s")
    _, hub = run(*new, "--type", "project", "--title", "Alpha", "--field", "kind=system", vault=root)
    body = (root / hub["rel"]).read_text()
    assert "## Board" in body and "note.project == this" in body and "## Project notes" in body
    assert body.index("## Board") < body.index("## Goal") < body.index("## Log")
    for type_name, folder in [("task", "Tasks"), ("decision", "Decisions"), ("research", "Research"),
                              ("howto", "Workflows"), ("note", "Notes"), ("debug", "Debug"),
                              ("incident", "Incidents")]:  # fmt: skip
        extra = ("--field", "question=q") if type_name == "research" else ()
        code, made = run(*new, "--type", type_name, "--title", f"{type_name} one", "--field", "project=Alpha",
                         *extra, vault=root)  # fmt: skip
        assert code == 0 and made["rel"].startswith(f"Projects/Alpha/{folder}/"), (type_name, made)
    _, loose = run(*new, "--type", "decision", "--title", "Loose", vault=root)
    assert loose["rel"].startswith("Decisions/")

    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}

    _, again = run("setup", "extension", "--vault", str(root), "--from", str(PROJECTS / "extension"))
    assert again["commit"] is None and again["updated"] == []  # idempotent


def test_both_add_ons_together_keep_the_fixture_vault_valid(fixture_vault):
    s = schema.load(fixture_vault)  # the fixture vault has both extensions installed
    assert {"jira", "kind", "docs"} <= set(
        s.types["project"].fields
    )  # synapsidian-work and synapsidian-projects both widen it
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(fixture_vault)}
    assert {rel: p for rel, p in problems.items() if p} == {}


OLD_HUB = """---
type: project
created: 2026-10-01
summary: s
status: active
---
## Goal

Ship the thing.

## Status


## Log
"""
OLD_TASK = "---\ntype: task\ncreated: 2026-10-01\nsummary: s\nid: T1\nstatus: todo\npriority: low\n" \
           "project: '[[Beta]]'\n---\nSee [[Beta]].\n"  # fmt: skip


def test_installing_refiles_old_notes_and_an_old_hub_gets_its_board(run, tmp_path):
    root = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(root), "--name", "N", "--email", "e@x")
    # Written before synapsidian-projects: the hub flat in Projects/, its task flat in Tasks/.
    (root / "Projects").mkdir(exist_ok=True)
    (root / "Projects/Beta.md").write_text(OLD_HUB)
    (root / "Tasks/T1 Ship.md").write_text(OLD_TASK)
    (root / "Tasks/T2 Taken.md").write_text(OLD_TASK.replace("T1", "T2"))
    (root / "Projects/Beta/Tasks").mkdir(parents=True)
    (root / "Projects/Beta/Tasks/T2 Taken.md").write_text("someone else's file\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "old notes"], check=True)
    _, check = run("setup", "check", "--vault", str(root))
    assert check["unknown_types"] == {"project": 1}  # the core alone doesn't know projects

    code, out = run("setup", "extension", "--vault", str(root), "--from", str(PROJECTS / "extension"))

    assert code == 0, out
    assert {(m["from"], m["to"]) for m in out["refiled"]["moved"]} == {
        ("Projects/Beta.md", "Projects/Beta/Beta.md"),
        ("Tasks/T1 Ship.md", "Projects/Beta/Tasks/T1 Ship.md"),
    }
    assert out["refiled"]["skipped"] == [
        {"rel": "Tasks/T2 Taken.md", "to": "Projects/Beta/Tasks/T2 Taken.md", "why": "target exists"}
    ]
    log = subprocess.run(["git", "-C", str(root), "log", "-1", "--name-status", "--format=%s",
                          out["refiled"]["commit"]], capture_output=True, text=True).stdout  # fmt: skip
    assert log.startswith("synapsidian(setup): file notes into their folders") and "R100" in log  # moves, not copies

    hub = "Projects/Beta/Beta.md"
    board = bin_run("section", "Board")
    assert board.returncode == 0 and board.stdout.lstrip().startswith("```base") and "## " not in board.stdout
    code, filled = run("note", "fill", "--file", hub, "--section", "Board", "--before", "Goal",
                       stdin=board.stdout, vault=root)  # fmt: skip
    assert code == 0 and filled["status"] == "added"
    text = (root / hub).read_text()
    assert text.index("## Board") < text.index("## Goal") and "Ship the thing." in text
    assert frontmatter.parse(text).meta["type"] == "project"
    _, again = run("note", "fill", "--file", hub, "--section", "Board", stdin=board.stdout, vault=root)
    assert again["status"] == "kept"
    links = bin_run("section", "Links")
    assert links.returncode == 0 and "- Docs:" in links.stdout and "## " not in links.stdout
    code, filled = run("note", "fill", "--file", hub, "--section", "Links", "--before", "Status",
                       stdin=links.stdout, vault=root)  # fmt: skip
    assert code == 0 and filled["status"] == "added"
    _, again = run("note", "fill", "--file", hub, "--section", "Links", stdin=links.stdout, vault=root)
    assert again["status"] == "kept"

    _, check = run("setup", "check", "--vault", str(root))
    assert check["unknown_types"] == {} and check["schema_warnings"] == []


SCRIPT = PROJECTS / "scripts" / "projects.py"


def script(*args: str, stdin: str | None = None) -> tuple[int, object]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, proc.stdout


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def test_decisions_take_madr_statuses_and_numbers_count_per_project(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--type", "decision", "--field", "summary=s")
    for project in ("Alpha", "Beta"):
        run("note", "new", "--type", "project", "--title", project, "--field", "summary=s", vault=root)
    assert run(*new, "--title", "One", "--field", "project=Alpha", "--field", "number=1",
               "--field", "status=rejected", vault=root)[0] == 0  # fmt: skip
    code, two = run(*new, "--title", "Two", "--field", "project=[[Alpha|the alpha]]", "--field", "number=2",
                    "--field", "status=deprecated", vault=root)  # fmt: skip
    assert code == 0, two
    run(*new, "--title", "Other", "--field", "project=Beta", "--field", "number=7", vault=root)
    run(*new, "--title", "Unnumbered", "--field", "project=Alpha", vault=root)  # one /synapsidian:save wrote
    # An archived decision keeps its number taken.
    archived = root / "Archive" / two["rel"]
    archived.parent.mkdir(parents=True)
    (root / two["rel"]).rename(archived)
    archived.write_text(archived.read_text().replace("number: 2", "number: 5"))

    _, query = run("query", "notes", "--type", "decision", "--all", vault=root)
    assert script("decision-number", "--project", "alpha", stdin=json.dumps(query))[1] == {
        "ok": True, "project": "alpha", "number": 6, "numbered": 2,
    }  # fmt: skip
    assert script("decision-number", "--project", "Gamma", stdin=json.dumps(query))[1]["number"] == 1
    assert script("decision-number", "--project", "Alpha", stdin="not json")[0] == 2

    code, superseded = run(*new, "--title", "Three", "--field", "project=Alpha", "--field", "status=superseded",
                           "--field", "superseded_by=One", vault=root)  # fmt: skip
    assert code == 0 and frontmatter.parse((root / superseded["rel"]).read_text()).meta["superseded_by"] == "[[One]]"
    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root, include_cold=True)}
    assert {rel: p for rel, p in problems.items() if p} == {}


def test_without_the_add_on_madr_statuses_are_not_valid(run, vault):
    code, out = run("note", "new", "--type", "decision", "--title", "X", "--field", "summary=s",
                    "--field", "status=rejected", vault=vault)  # fmt: skip
    assert code == 2 and "rejected" in out["error"]


def make_repo(root: Path) -> Path:
    files = {
        "README.md": "Intro line\n\n# Web app\n\nWhat it does.\n",
        "package.json": json.dumps({"name": "web-app", "version": "1.2.0", "workspaces": ["apps/*"],
                                    "dependencies": {"vue": "^3.5.0", "pinia": "^3.0.0"},
                                    "devDependencies": {"vite": "^7.0.0"}, "scripts": {"build": "vite build"}}),
        "apps/api/pyproject.toml": '[project]\nname = "api"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'
                                   'dependencies = ["httpx>=0.27", "pyyaml"]\n',
        "apps/api/src/main.py": "print('hi')\n",
        "apps/web/src/App.vue": "<template />\n",
        "apps/web/src/main.ts": "export {}\n",
        "docs/adr/0001-use-vue.md": "# Use Vue\n",
        "docs/guide.txt": "plain\n",
        ".github/workflows/ci.yml": "on: push\n",
        "node_modules/left-pad/package.json": '{"name": "left-pad"}',
    }  # fmt: skip
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git(root.parent, "init", "-q", "-b", "main", str(root))
    git(root, "config", "user.name", "T")
    git(root, "config", "user.email", "t@example.com")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "first")
    git(root, "remote", "add", "origin", "https://someone:s3cr3t-token@example.com/org/web-app.git")
    return root


def test_scan_reads_a_repository_and_changes_nothing_in_it(tmp_path):
    repo = make_repo(tmp_path / "web-app")
    first = git(repo, "rev-parse", "--short", "HEAD").strip()
    (repo / "apps/web/src/Chart.vue").write_text("<template />\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "feat: chart")
    (repo / "scratch.txt").write_text("untracked, uncommitted\n")  # the user's work in progress
    status = git(repo, "status", "--porcelain")
    index = (repo / ".git/index").stat().st_mtime_ns  # after status, which may refresh it itself

    code, facts = script("scan", "--repo", str(repo), "--docs", "docs", "--docs", "missing", "--since", first)

    assert code == 0, facts
    assert facts["branch"] == "main" and facts["origin"] == "https://example.com/org/web-app.git"
    assert {m["path"] for m in facts["manifests"]} == {"package.json", "apps/api/pyproject.toml"}  # not node_modules
    web = next(m for m in facts["manifests"] if m["path"] == "package.json")
    assert web["dependencies"] == ["pinia", "vue"] and web["dev_dependencies"] == 1
    api = next(m for m in facts["manifests"] if m["path"] == "apps/api/pyproject.toml")
    assert api["dependencies"] == ["httpx", "pyyaml"] and api["requires_python"] == ">=3.12"
    assert facts["readme"] == {"path": "README.md", "title": "Web app"}
    assert facts["docs"][0] == {"path": "docs", "exists": True, "markdown": 1, "files": ["docs/adr/0001-use-vue.md"]}
    assert facts["docs"][1]["exists"] is False
    assert facts["ci"] == [".github/workflows/ci.yml"]
    assert facts["layout"][0] == {"folder": "apps", "files": 5, "children": [
        {"folder": "web", "files": 3}, {"folder": "api", "files": 2}]}  # fmt: skip
    assert facts["since"]["count"] == 1 and facts["since"]["changed_folders"] == {"apps": 1}
    assert [c["subject"] for c in facts["recent"]] == ["feat: chart", "first"]

    _, md = script("scan", "--repo", str(repo), "--markdown")
    assert md.startswith("- **Scanned:** commit `") and "s3cr3t" not in md and "web-app; 1.2.0" in md

    # One app of a monorepo: only its own files, manifests and commits.
    _, app = script("scan", "--repo", str(repo / "apps/web"))
    assert app["files"] == 3 and app["manifests"] == [] and [c["subject"] for c in app["recent"]] == [
        "feat: chart", "first"]  # fmt: skip

    assert (repo / ".git/index").stat().st_mtime_ns == index  # not even the index refreshed
    assert git(repo, "status", "--porcelain") == status  # nothing written, staged or removed


def test_scan_refuses_urls_and_folders_outside_git(tmp_path):
    code, out = script("scan", "--repo", "https://example.com/org/web-app.git")
    assert code == 2 and "local clone" in out["error"]
    assert script("scan", "--repo", "git@example.com:org/web-app.git")[0] == 2
    (tmp_path / "plain").mkdir()
    code, out = script("scan", "--repo", str(tmp_path / "plain"))
    assert code == 2 and "not in a git repository" in out["error"]
    via_bin = bin_run("scan", "--repo", "https://example.com/x.git")
    assert via_bin.returncode == 2 and "local clone" in via_bin.stdout


def test_hub_gets_a_hashed_repository_section_before_key_decisions(run, projects_vault, tmp_path):
    repo = make_repo(tmp_path / "web-app")
    _, hub = run("note", "new", "--type", "project", "--title", "Web app", "--field", "summary=s",
                 "--field", "kind=repository", "--field", f"repo={repo}", vault=projects_vault)  # fmt: skip
    _, md = script("scan", "--repo", str(repo), "--markdown")
    block = ("block", "set", "--file", hub["rel"], "--name", "repository", "--section", "Repository",
             "--before", "Key decisions", "--hash")  # fmt: skip

    assert run(*block, stdin=md, vault=projects_vault)[0] == 0
    text = (projects_vault / hub["rel"]).read_text()
    assert text.index("## Status") < text.index("## Repository") < text.index("## Key decisions")
    assert "<!-- @generated:repository sha=" in text and "web-app; 1.2.0" in text

    assert run(*block, stdin=md + "- more\n", vault=projects_vault)[0] == 0  # a refresh rewrites it
    path = projects_vault / hub["rel"]
    path.write_text(path.read_text().replace("- more", "- my own line"))
    code, out = run(*block, stdin=md, vault=projects_vault)
    assert code == 4 and "my own line" in out["current"]  # a hand edit is never overwritten silently
    commit = git(repo, "rev-parse", "--short", "HEAD").strip()
    assert run("note", "set", "--file", hub["rel"], "--field", f"scanned_commit={commit}", vault=projects_vault)[0] == 0
    assert run("note", "set", "--file", hub["rel"], "--field", "scanned_commit=main", vault=projects_vault)[0] == 2


MAPS = PROJECTS / "scripts" / "maps.py"
HUB_WITH_QUESTIONS = "\n## Open questions\n\n- Which payment API?\n- None of the others\n\n## Project notes\n"


def draw(run, root: Path, project: str = "Alpha", *extra: str) -> dict:
    _, query = run("query", "notes", "--limit", "100000", vault=root)
    proc = subprocess.run([sys.executable, str(MAPS), "--project", project, "--now", "1", *extra],
                          input=json.dumps(query), capture_output=True, text=True)  # fmt: skip
    return {"code": proc.returncode, **json.loads(proc.stdout)}


def scene(path: Path) -> tuple[str, list[dict]]:
    import re

    text = path.read_text()
    return text, json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))["elements"]


def keyed(elements: list[dict]) -> dict[str, dict]:
    return {e["customData"]["synapsidian"]: e for e in elements if (e.get("customData") or {}).get("synapsidian")}


def test_map_draws_the_project_and_a_refresh_keeps_what_the_user_changed(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s", "--field", "project=Alpha")
    _, hub = run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    hub_path = root / hub["rel"]
    hub_path.write_text(hub_path.read_text().replace("\n## Open questions\n\n\n## Project notes\n", HUB_WITH_QUESTIONS))
    _, t1 = run(*new, "--type", "task", "--title", "Ship it", vault=root)
    _, t2 = run(*new, "--type", "task", "--title", "Plan, then test", vault=root)
    run(*new, "--type", "task", "--title", "Old", "--field", "status=done", vault=root)
    run(*new, "--type", "decision", "--title", "Use Vue", "--field", "number=1", vault=root)
    run(*new, "--type", "decision", "--title", "Use jQuery", "--field", "status=superseded", vault=root)
    run(*new, "--type", "spec", "--title", "Alpha checkout", vault=root)
    run("note", "new", "--type", "task", "--title", "Elsewhere", "--field", "summary=s", vault=root)

    first = draw(run, root)

    assert first["code"] == 0 and first["created"] and first["rel"] == "Projects/Alpha/Maps/Alpha map.excalidraw.md"
    assert first["link"] == "[[Alpha map.excalidraw]]"
    path = root / first["rel"]
    text, elements = scene(path)
    nodes = keyed(elements)
    today = dt.date.today().isoformat()
    assert {"hub", "branch:Open tasks", "branch:Decisions", "branch:Specs", "branch:Open questions",
            f"note:{t1['id']} Ship it", f"note:{today} Use Vue"} <= set(nodes)  # fmt: skip
    assert not [k for k in nodes if "Old" in k or "jQuery" in k or "Elsewhere" in k]  # closed, superseded, other
    assert [n["text"] for k, n in nodes.items() if k.startswith("question:")] == ["Which payment API?"]
    assert nodes[f"note:{today} Use Vue"]["text"] == f"[[{today} Use Vue|#1 Use Vue]]"
    plan_key = f"note:{t2['id']} Plan, then test"
    assert f"[[{t2['id']} Plan, then test]] ^{nodes[plan_key]['id']}" in text
    assert text.startswith("---\n\nexcalidraw-plugin: parsed\n") and "%%\n## Drawing\n```json\n" in text
    assert len({e["id"] for e in elements}) == len(elements) and all(len(e["id"]) == 8 for e in elements)
    assert draw(run, root)["changed"] is False  # nothing new: nothing written

    # What Obsidian does on save, and what a user does: new ids, the label shown in `text`,
    # a node moved, an own shape with an arrow to a task node.
    ids = {e["id"]: f"user{i:04d}" for i, e in enumerate(elements)}
    raw_text = path.read_text()
    for old, new_id in ids.items():
        raw_text = raw_text.replace(old, new_id)
    path.write_text(raw_text)
    text, elements = scene(path)
    nodes = keyed(elements)
    spec_node = nodes["note:Alpha checkout"]
    spec_node["x"], spec_node["y"] = 900.0, 700.0
    ship = nodes[f"note:{t1['id']} Ship it"]
    ship["text"] = ship["originalText"] = "Ship it"
    mine = {"id": "mineAAAA", "type": "rectangle", "x": -900, "y": -900, "width": 50, "height": 50,
            "boundElements": [{"type": "arrow", "id": "mineBBBB"}]}  # fmt: skip
    mine_arrow = {"id": "mineBBBB", "type": "arrow", "x": 0, "y": 0, "points": [[0, 0], [1, 1]],
                  "startBinding": {"elementId": "mineAAAA"}, "endBinding": {"elementId": ship["id"]}}  # fmt: skip
    elements += [mine, mine_arrow]
    path.write_text(text.split("```json\n")[0] + "```json\n" + json.dumps({"type": "excalidraw", "elements": elements})
                    + "\n```\n%%\n")  # fmt: skip
    after_save = draw(run, root)  # the plugin's own save reads back: no node added, updated or removed
    assert after_save["code"] == 0
    assert (after_save["added"], after_save["updated"], after_save["removed"]) == ([], [], [])

    run("note", "set", "--file", t1["rel"], "--field", "status=done", vault=root)
    _, t9 = run(*new, "--type", "task", "--title", "Brand new", vault=root)
    again = draw(run, root)

    assert again["code"] == 0 and f"note:{t9['id']} Brand new" in again["added"]
    assert again["removed"] == [f"note:{t1['id']} Ship it"]
    text, elements = scene(path)
    nodes = keyed(elements)
    assert (nodes["note:Alpha checkout"]["x"], nodes["note:Alpha checkout"]["y"]) == (900.0, 700.0)  # kept
    edge = nodes["edge:branch:Specs>note:Alpha checkout"]
    assert edge["x"] + edge["points"][1][0] > 850  # the arrow follows the moved node
    by_id = {e["id"]: e for e in elements}
    assert by_id["mineAAAA"]["x"] == -900 and by_id["mineBBBB"]["endBinding"] is None  # the user's, unbound
    assert by_id["mineAAAA"]["boundElements"] == [{"type": "arrow", "id": "mineBBBB"}]
    plan = nodes[f"note:{t2['id']} Plan, then test"]
    assert nodes[f"note:{t9['id']} Brand new"]["y"] > plan["y"]  # under its sibling
    assert plan["id"].startswith("user")  # the ids Obsidian gave the nodes are kept
    assert draw(run, root)["changed"] is False


def test_map_colours_by_status_follows_renames_and_links_what_it_leaves_out(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s", "--field", "project=Alpha")
    _, hub = run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    hub_path = root / hub["rel"]
    hub_path.write_text(hub_path.read_text().replace("\n## Open questions\n\n\n## Project notes\n", HUB_WITH_QUESTIONS))
    _, doing = run(*new, "--type", "task", "--title", "Ship it", "--field", "status=doing", vault=root)
    _, todo = run(*new, "--type", "task", "--title", "Write the release notes", vault=root)
    run(*new, "--type", "spec", "--title", "Alpha old API", "--field", "status=retired", vault=root)
    assert run(*new, "--type", "thinking", "--title", "Why a monorepo", "--field", "kind=topic", vault=root)[0] == 0

    path = root / draw(run, root)["rel"]
    nodes = keyed(scene(path)[1])
    assert nodes[f"note:{doing['id']} Ship it"]["strokeColor"] == "#1971c2"
    assert nodes[f"note:{todo['id']} Write the release notes"]["strokeColor"] == "#1e1e1e"
    thinking = f"note:{dt.date.today().isoformat()} topic Why a monorepo"
    assert thinking in nodes and "note:Alpha old API" not in nodes  # thinking in, retired out

    # The user moves the todo task and recolours the doing one; then both change status, the todo
    # task is renamed and the open question reworded.
    text, elements = scene(path)
    for e in elements:
        key = (e.get("customData") or {}).get("synapsidian")
        if key == f"note:{todo['id']} Write the release notes":
            e["x"], e["y"] = 1234.0, 567.0
        if key == f"note:{doing['id']} Ship it":
            e["strokeColor"] = "#2f9e44"
    path.write_text(text.split("```json\n")[0] + "```json\n" + json.dumps({"type": "excalidraw", "elements": elements})
                    + "\n```\n%%\n")  # fmt: skip
    question_key = next(k for k in nodes if k.startswith("question:"))
    hub_path.write_text(hub_path.read_text().replace("Which payment API?", "Which payments API?"))
    run("note", "set", "--file", doing["rel"], "--field", "status=waiting", vault=root)
    run("note", "set", "--file", todo["rel"], "--field", "status=doing", vault=root)
    renamed_rel = todo["rel"].replace("Write the release notes", "Write the release note")
    (root / renamed_rel).write_text((root / todo["rel"]).read_text())
    (root / todo["rel"]).unlink()

    again = draw(run, root)
    assert again["code"] == 0 and again["added"] == [] and again["removed"] == []
    nodes = keyed(scene(path)[1])
    renamed = nodes[f"note:{todo['id']} Write the release note"]
    assert (renamed["x"], renamed["y"], renamed["strokeColor"]) == (1234.0, 567.0, "#1971c2")  # kept, recoloured
    assert nodes[f"note:{doing['id']} Ship it"]["strokeColor"] == "#2f9e44"  # the user's colour wins
    assert question_key not in nodes
    assert [n["text"] for k, n in nodes.items() if k.startswith("question:")] == ["Which payments API?"]
    assert f"edge:branch:Open tasks>note:{todo['id']} Write the release note" in nodes
    assert draw(run, root)["changed"] is False

    # A spec retired next to a similar new one is two notes, not a rename: its title is still in the vault.
    _, spec = run(*new, "--type", "spec", "--title", "Alpha auth flow", vault=root)
    draw(run, root)
    run("note", "set", "--file", spec["rel"], "--field", "status=retired", vault=root)
    run(*new, "--type", "spec", "--title", "Alpha auth flow v2", vault=root)
    swap = draw(run, root)
    assert "note:Alpha auth flow v2" in swap["added"] and "note:Alpha auth flow" in swap["removed"]

    capped = keyed(scene(root / draw(run, root, "Alpha", "--max-leaves", "1")["rel"])[1])
    assert capped["more:Open tasks"]["text"] == "[[Alpha#Board|+1 more]]"
    assert "more:Open tasks" not in keyed(scene(root / draw(run, root, "Alpha", "--max-leaves", "0")["rel"])[1])
    assert draw(run, root, "Alpha", "--max-leaves", "-1")["code"] == 2


def boxes_overlap(a: dict, b: dict) -> bool:
    return (a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"]
            and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"])  # fmt: skip


def test_map_refreshes_never_draw_a_new_node_over_a_box_already_there(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s", "--field", "project=Alpha")
    run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    # Open tasks and Specs share the right side, Specs under Open tasks; Decisions and Notes the left.
    run(*new, "--type", "task", "--title", "Task 0", vault=root)
    run(*new, "--type", "decision", "--title", "Decision 0", vault=root)
    run(*new, "--type", "spec", "--title", "Spec first", vault=root)
    run(*new, "--type", "note", "--title", "A much longer note title than the others", vault=root)
    path = root / draw(run, root, "Alpha", "--max-leaves", "0")["rel"]

    # The user's own box just under the first task, where the next task would go.
    text, elements = scene(path)
    nodes = keyed(elements)
    assert nodes["branch:Decisions"]["x"] < nodes["hub"]["x"] < nodes["branch:Open tasks"]["x"]  # both sides
    first = nodes[next(k for k in nodes if k.startswith("note:") and "Task 0" in k)]
    mine = {"id": "mineAAAA", "type": "rectangle", "x": first["x"], "y": first["y"] + first["height"] + 10,
            "width": 120, "height": 60}  # fmt: skip
    elements.append(mine)
    path.write_text(text.split("```json\n")[0] + "```json\n" + json.dumps({"type": "excalidraw", "elements": elements})
                    + "\n```\n%%\n")  # fmt: skip

    for batch in range(3):  # many refreshes, each adding leaves to both branches on each side
        for i in range(6):
            run(*new, "--type", "task", "--title", f"Task {batch}{i}", vault=root)
            run(*new, "--type", "decision", "--title", f"Decision {batch}{i} with a wider label", vault=root)
        run(*new, "--type", "spec", "--title", f"Spec {batch}", vault=root)
        run(*new, "--type", "note", "--title", f"Note {batch}", vault=root)
        before = {e["id"]: (e["x"], e["y"]) for e in scene(path)[1] if e["type"] != "arrow"}
        assert draw(run, root, "Alpha", "--max-leaves", "0")["code"] == 0
        after = scene(path)[1]
        assert {e["id"]: (e["x"], e["y"]) for e in after if e["id"] in before} == before  # nothing moved

    drawn = [e for e in after if e["type"] != "arrow" and not e.get("containerId")]
    assert len([e for e in drawn if (e.get("customData") or {}).get("synapsidian", "").startswith("note:")]) == 46

    def key(e):
        return e.get("customData", {}).get("synapsidian", e["id"])

    clashes = [(key(a), key(b))
               for i, a in enumerate(drawn) for b in drawn[i + 1:] if boxes_overlap(a, b)]  # fmt: skip
    assert clashes == []


def test_milestones_live_in_their_project_hold_its_tasks_and_open_ones_are_mapped(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s")
    _, hub = run(*new, "--type", "project", "--title", "Alpha", vault=root)
    hub_text = (root / hub["rel"]).read_text()
    assert hub_text.index("## Status") < hub_text.index("## Roadmap") < hub_text.index("## Key decisions")
    assert "name: Milestones" in hub_text and "      - blocked_by\n" in hub_text
    code, out = run(*new, "--type", "milestone", "--title", "Loose", vault=root)
    assert code == 2 and "project" in out["error"]  # always a project's

    _, beta = run(*new, "--type", "milestone", "--title", "Alpha beta", "--field", "project=Alpha",
                  "--field", "target=2026-12-01", vault=root)  # fmt: skip
    assert beta["rel"] == "Projects/Alpha/Milestones/Alpha beta.md"
    text = (root / beta["rel"]).read_text()
    assert frontmatter.parse(text).meta["status"] == "planned"
    assert HEADING.findall(text) == ["## Goal", "## Exit criteria", "## Tasks", "## Flow", "## Log"]
    assert "note.milestone == this" in text
    _, task = run(*new, "--type", "task", "--title", "Ship it", "--field", "project=Alpha",
                  "--field", "milestone=[[Alpha beta]]", vault=root)  # fmt: skip
    assert task["rel"].startswith("Projects/Alpha/Tasks/")
    run(*new, "--type", "milestone", "--title", "Alpha alpha", "--field", "project=Alpha", "--field", "status=done",
        vault=root)  # fmt: skip
    _, closed = run("note", "set", "--file", beta["rel"], "--field", "status=active", vault=root)
    assert closed["ok"]

    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}

    nodes = keyed(scene(root / draw(run, root)["rel"])[1])
    assert nodes["note:Alpha beta"]["text"] == "[[Alpha beta|Alpha beta (2026-12-01)]]"
    assert nodes["note:Alpha beta"]["strokeColor"] == "#1971c2"  # active
    assert "note:Alpha alpha" not in nodes  # done: off the map


def test_a_hub_has_risks_people_and_goals_and_an_older_hub_gets_its_risks(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s")
    run(*new, "--type", "person", "--title", "Alex", vault=root)
    run(*new, "--type", "goal", "--title", "Run a marathon", vault=root)
    _, hub = run(*new, "--type", "project", "--title", "Alpha", "--field", "people=[[Alex]]",
                 "--field", "goals=[[Run a marathon]]", vault=root)  # fmt: skip
    path = root / hub["rel"]
    text = path.read_text()
    assert text.index("## Key decisions") < text.index("## Risks") < text.index("## Open questions")
    meta = frontmatter.parse(text).meta
    assert (meta["people"], meta["goals"]) == (["[[Alex]]"], ["[[Run a marathon]]"])
    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}

    risks = bin_run("section", "Risks")
    assert risks.returncode == 0 and "likelihood / impact" in risks.stdout and "## " not in risks.stdout
    path.write_text(text.replace("## Risks\n" + risks.stdout, ""))  # a hub made before 0.11.0
    assert "## Risks" not in path.read_text()
    code, filled = run("note", "fill", "--file", hub["rel"], "--section", "Risks", "--before", "Open questions",
                       stdin=risks.stdout, vault=root)  # fmt: skip
    assert code == 0 and filled["status"] == "added"
    text = path.read_text()
    assert text.index("## Key decisions") < text.index("## Risks") < text.index("## Open questions")


FLOWS = PROJECTS / "scripts" / "flows.py"


def flow(run, root: Path, *args: str) -> tuple[int, dict]:
    _, query = run("query", "notes", "--limit", "100000", vault=root)
    proc = subprocess.run([sys.executable, str(FLOWS), "--project", "Alpha", *args],
                          input=json.dumps(query), capture_output=True, text=True)  # fmt: skip
    return proc.returncode, json.loads(proc.stdout)


def test_flows_draw_the_roadmap_and_a_milestones_tasks_in_order(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s", "--field", "project=Alpha")
    run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    assert flow(run, root)[1]["markdown"] == "No milestones or tasks waiting on each other yet."

    run(*new, "--type", "milestone", "--title", "Alpha beta", "--field", "start=2026-11-01",
        "--field", "target=2026-12-01", "--field", "status=active", vault=root)  # fmt: skip
    run(*new, "--type", "milestone", "--title", "Alpha 1.0", vault=root)
    run(*new, "--type", "milestone", "--title", "Alpha gone", "--field", "target=2026-12-01",
        "--field", "status=dropped", vault=root)  # fmt: skip
    run(*new, "--type", "milestone", "--title", "Alpha alpha", "--field", "start=2026-10-30",
        "--field", "status=done", "--field", "done_on=2026-10-30", vault=root)  # fmt: skip  # no target, one day
    beta = "--field", "milestone=[[Alpha beta]]"
    _, api = run(*new, "--type", "task", "--title", "Pick the API (v2, & the docs)", *beta, vault=root)
    api_title = api["rel"].rsplit("/", 1)[-1].removesuffix(".md")
    _, ship = run(*new, "--type", "task", "--title", "Ship it", *beta, "--field", f"blocked_by=[[{api_title}]]",
                  "--field", "status=doing", vault=root)  # fmt: skip
    _, alone = run(*new, "--type", "task", "--title", "Unrelated", vault=root)
    _, old = run(*new, "--type", "task", "--title", "Old step", "--field", "status=done", vault=root)
    _, after = run(*new, "--type", "task", "--title", "After the old step",
                   "--field", f"blocked_by=[[{old['id']} Old step]]", vault=root)  # fmt: skip

    code, out = flow(run, root)
    assert code == 0 and out["tasks"] == 2 and out["edges"] == 1 and out["cycles"] == []
    md = out["markdown"]
    assert "    inclusiveEndDates\n" in md  # a bar ends at the end of its last day
    assert "    Alpha alpha :done, m1, 2026-10-30, 2026-10-30" in md  # done: ends on done_on, target or not
    assert "    Alpha beta :active, m2, 2026-11-01, 2026-12-01" in md
    assert "Alpha gone" not in md and out["undated"] == ["Alpha 1.0"]
    assert "- No target date yet: [[Alpha 1.0]]" in md
    assert f'n1["{api_title}"]' in md and 'subgraph g1["Alpha beta"]' in md
    assert "    n1 --> n2" in md and "class n2 doing" in md and "class n1,n2 internal-link" in md
    assert "classDef doing fill:#d0ebff,stroke:#1971c2,color:#1e1e1e" in md  # dark text, not the link colour
    assert alone["id"] not in md  # waits on nothing, nothing waits on it
    assert after["id"] not in md  # waits only on a done task: free to start

    sys.path.insert(0, str(FLOWS.parent))
    import flows

    assert flows.label('A "new" <b> #12') == "A #quot;new#quot; #lt;b#gt; #35;12"  # Mermaid's entity codes
    assert flows.gantt_text("Beta: cut #1; then") == "Beta - cut -1 - then"  # `:` would end a gantt name

    code, out = flow(run, root, "--milestone", "Alpha beta")
    assert code == 0 and out["tasks"] == 2 and out["markdown"].startswith("```mermaid\nflowchart LR\n")

    # A cycle is drawn and named, since nothing in it can start.
    run("note", "set", "--file", api["rel"], "--field", f"blocked_by=[[{ship['id']} Ship it]]", vault=root)
    code, out = flow(run, root)
    assert code == 0 and len(out["cycles"]) == 1 and "⚠ Waiting on each other" in out["markdown"]

    _, change = run(*new, "--type", "change", "--title", "Move to API v2", "--field", f"tasks=[[{ship['id']} Ship it]]",
                    vault=root)  # fmt: skip
    code, out = flow(run, root, "--change", change["rel"].rsplit("/", 1)[-1].removesuffix(".md"))
    assert code == 0 and out["tasks"] == 1 and out["edges"] == 1  # its task and what that waits on

    # A blocker in no project, or another one, still holds the task back and is drawn.
    _, outside = run("note", "new", "--type", "task", "--title", "Open the account", "--field", "summary=s", vault=root)
    run("note", "set", "--file", alone["rel"], "--field", f"blocked_by=[[{outside['id']} Open the account]]",
        vault=root)  # fmt: skip
    md = flow(run, root)[1]["markdown"]
    assert f'"{outside["id"]} Open the account"' in md and f'"{alone["id"]} Unrelated"' in md

    # A milestone of another project is refused rather than drawn into this one.
    run("note", "new", "--type", "project", "--title", "Beta", "--field", "summary=s", vault=root)
    run("note", "new", "--type", "milestone", "--title", "Beta one", "--field", "summary=s", "--field", "project=Beta",
        vault=root)  # fmt: skip
    assert flow(run, root, "--milestone", "Beta one")[0] == 2
    proc =subprocess.run([sys.executable, str(FLOWS), "--project", "Alpha", "--markdown"], input="{}",
                          capture_output=True, text=True)  # fmt: skip
    assert proc.returncode == 2 and flow(run, root, "--milestone", "Nope")[0] == 2


PROGRESS = PROJECTS / "scripts" / "progress.py"


def progress(run, root: Path, *args: str) -> tuple[int, dict | str]:
    _, query = run("query", "notes", "--limit", "100000", vault=root)
    proc = subprocess.run([sys.executable, str(PROGRESS), "--project", "Alpha", "--today", "2026-11-03", *args],
                          input=json.dumps(query), capture_output=True, text=True)  # fmt: skip
    out = proc.stdout.strip()
    return proc.returncode, json.loads(out) if out.startswith("{") else out


def test_progress_counts_what_closed_since_the_last_log_line_what_waits_and_each_milestone(run, projects_vault):
    root = projects_vault
    new = ("note", "new", "--field", "summary=s", "--field", "project=Alpha")
    _, hub = run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    hub_path = root / hub["rel"]
    log = "- 2026-10-20: project created\n- 2026-10-27: status: beta planned\n- 2026-10-31: refreshed\n"
    hub_path.write_text(hub_path.read_text() + log)

    beta = ("--field", "milestone=[[Alpha beta]]")
    done = ("--field", "status=done")
    run(*new, "--type", "milestone", "--title", "Alpha beta", "--field", "target=2026-11-13",
        "--field", "status=active", vault=root)  # fmt: skip
    run(*new, "--type", "milestone", "--title", "Alpha alpha", *done, "--field", "done_on=2026-10-30", vault=root)
    run(*new, "--type", "milestone", "--title", "Alpha later", vault=root)
    _, old = run(*new, "--type", "task", "--title", "Old work", *done, "--field", "done_on=2026-10-27", *beta,
                 vault=root)  # fmt: skip
    _, api = run(*new, "--type", "task", "--title", "Pick the API", *done, "--field", "done_on=2026-10-29", *beta,
                 vault=root)  # fmt: skip
    _, ship = run(*new, "--type", "task", "--title", "Ship it", "--field", "status=doing", *beta, vault=root)
    _, other = run("note", "new", "--type", "task", "--title", "Open the account", "--field", "summary=s", vault=root)
    waits = f"blocked_by=[[{ship['id']} Ship it]],[[{api['id']} Pick the API]],[[{other['id']} Open the account]]"
    _, docs = run(*new, "--type", "task", "--title", "Write the docs", *beta, "--field", waits, vault=root)
    run(*new, "--type", "task", "--title", "Gone", "--field", "status=dropped", *beta, vault=root)
    run(*new, "--type", "change", "--title", "Move to v2", *done, "--field", "done_on=2026-11-02", vault=root)
    run(*new, "--type", "change", "--title", "Move to v3", vault=root)
    run(*new, "--type", "decision", "--title", "Use v2", "--field", "status=accepted", vault=root)
    run(*new, "--type", "decision", "--title", "Maybe v3", "--field", "status=proposed", vault=root)
    run("note", "new", "--type", "task", "--title", "Elsewhere", *done, "--field", "summary=s", vault=root)

    today = dt.date.today()  # changes and decisions are named by the day they were made, so the window reaches it
    code, out = progress(run, root, "--until", str(today))
    # The day after the last status line: what it reported isn't counted again, and a refresh doesn't move it.
    assert code == 0 and (out["since"], out["until"]) == ("2026-10-28", str(today))
    closed = out["closed"]
    assert [t["title"] for t in closed["tasks"]] == [f"{api['id']} Pick the API"]  # Old work closed before
    assert [m["title"] for m in closed["milestones"]] == ["Alpha alpha"]
    assert [c["title"] for c in closed["changes"]] == [f"{today} Move to v2"]  # by `done_on`
    assert [d["title"] for d in closed["decisions"]] == [f"{today} Use v2"]  # by `created`
    assert out["in_progress"] == [{"title": f"{ship['id']} Ship it", "status": "doing"}]
    assert out["blocked"] == [{"title": f"{docs['id']} Write the docs", "status": "todo",
                               "blocked_by": [f"{ship['id']} Ship it", f"{other['id']} Open the account"]}]  # fmt: skip
    # A done blocker no longer counts; an open one outside the project does.
    assert out["milestones"] == [
        {"title": "Alpha beta", "status": "active", "target": "2026-11-13", "done": 2, "total": 4,
         "days_to_target": 10},
        {"title": "Alpha later", "status": "planned", "target": None, "done": 0, "total": 0, "days_to_target": None},
    ]  # fmt: skip  # the dropped task doesn't count, the done milestone isn't open
    assert out["open"]["changes"] == [{"title": f"{today} Move to v3", "status": "proposed"}]
    assert out["open"]["decisions"] == [{"title": f"{today} Maybe v3"}]
    assert {t["title"] for t in out["open"]["tasks"]} == {f"{ship['id']} Ship it", f"{docs['id']} Write the docs"}
    assert out["summary"] == (
        f"[[Alpha]]: 1 task done, [[Alpha alpha]] reached, [[{today} Move to v2]] done, "
        "1 decision accepted; 1 in progress, 1 blocked; next [[Alpha beta]] 2/4, 10 days left"
    )

    code, out = progress(run, root, "--since", "2026-10-01", "--until", "2026-10-31")  # a review's period
    assert [t["title"] for t in out["closed"]["tasks"]] == [f"{old['id']} Old work", f"{api['id']} Pick the API"]
    assert out["closed"]["changes"] == [] and out["closed"]["decisions"] == []
    code, line = progress(run, root, "--today", "2026-11-20", "--markdown")
    assert line.endswith("next [[Alpha beta]] 2/4, 7 days past target")
    assert progress(run, root, "--project", "Nope")[0] == 2


def test_closing_a_project_moves_a_task_out_of_its_milestone_and_writes_a_retro_before_the_log(run, projects_vault):
    """The steps `project close` runs (D150): settle what is open, a Retro section, status done."""
    root = projects_vault
    new = ("note", "new", "--field", "summary=s")
    _, hub = run(*new, "--type", "project", "--title", "Alpha", vault=root)
    run(*new, "--type", "project", "--title", "Beta", vault=root)
    run(*new, "--type", "milestone", "--title", "Alpha beta", "--field", "project=Alpha", vault=root)
    _, task = run(*new, "--type", "task", "--title", "Keep going", "--field", "project=Alpha",
                  "--field", "milestone=[[Alpha beta]]", vault=root)  # fmt: skip
    assert [t["title"] for t in progress(run, root, "--since", "2026-01-01")[1]["open"]["tasks"]] == [
        f"{task['id']} Keep going"
    ]

    code, moved = run("note", "set", "--file", task["rel"], "--field", "project=Beta", "--field", "milestone=",
                      vault=root)  # fmt: skip
    assert code == 0 and moved["rel"].startswith("Projects/Beta/Tasks/")
    assert "milestone" not in frontmatter.parse((root / moved["rel"]).read_text()).meta
    run("note", "set", "--file", "Projects/Alpha/Milestones/Alpha beta.md", "--field", "status=dropped", vault=root)
    open_now = progress(run, root, "--since", "2026-01-01")[1]["open"]
    assert open_now == {"tasks": [], "milestones": [], "changes": [], "decisions": []}

    retro = "Closed 2026-11-03 after 14 days.\n\n**Went well:**\n- the beta\n"
    fill = ("note", "fill", "--file", hub["rel"], "--section", "Retro", "--before", "Log")
    assert run(*fill, stdin=retro, vault=root)[0] == 0
    run("note", "set", "--file", hub["rel"], "--field", "status=done", vault=root)
    text = (root / hub["rel"]).read_text()
    assert text.index("## Project notes") < text.index("## Retro") < text.index("Closed 2026-11-03")
    assert text.index("Closed 2026-11-03") < text.index("## Log")
    assert frontmatter.parse(text).meta["status"] == "done"
    assert schema.validate(frontmatter.parse(text).meta, hub["rel"], schema.load(root)) == []


def test_map_refuses_a_compressed_drawing_and_an_unknown_project(run, projects_vault):
    run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=projects_vault)
    maps = projects_vault / "Projects/Alpha/Maps"
    maps.mkdir()
    compressed = "# Excalidraw Data\n%%\n## Drawing\n```compressed-json\nN4Ig\n```\n%%\n"
    (maps / "Alpha map.excalidraw.md").write_text(compressed)
    out = draw(run, projects_vault)
    assert out["code"] == 2 and "compressed" in out["error"]
    assert draw(run, projects_vault, "Nope")["code"] == 2


def test_map_reads_the_scene_under_drawing_not_a_json_snippet_above_it(run, projects_vault):
    run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=projects_vault)
    first = draw(run, projects_vault)
    path = projects_vault / first["rel"]
    snippet = '```json\n{"mine": true}\n```\n\n'
    path.write_text(path.read_text().replace("## Text Elements", snippet + "## Text Elements", 1))
    again = draw(run, projects_vault)
    assert again["code"] == 0 and again["changed"] is False
    assert snippet in path.read_text()


def test_specs_and_changes_live_in_their_project(run, projects_vault):
    root = projects_vault
    run("note", "new", "--type", "project", "--title", "Alpha", "--field", "summary=s", vault=root)
    code, out = run("note", "new", "--type", "spec", "--title", "Loose spec", "--field", "summary=s", vault=root)
    assert code == 2 and "project" in out["error"]  # a spec always belongs to a project
    _, spec = run("note", "new", "--type", "spec", "--title", "Alpha API", "--field", "summary=s",
                  "--field", "project=Alpha", vault=root)  # fmt: skip
    assert spec["rel"] == "Projects/Alpha/Specs/Alpha API.md"
    assert "## Requirements" in (root / spec["rel"]).read_text()
    _, task = run("note", "new", "--type", "task", "--title", "Plan, then test", "--field", "summary=s",
                  "--field", "project=Alpha", vault=root)  # fmt: skip
    _, change = run("note", "new", "--type", "change", "--title", "Move to API v2", "--field", "summary=s",
                    "--field", "project=Alpha", "--field", "specs=[[Alpha API]]",
                    "--field", f"tasks=[[{task['id']} Plan, then test]],[[{task['id']} Plan, then test]]",
                    vault=root)  # fmt: skip
    assert change["rel"].startswith("Projects/Alpha/Changes/") and change["rel"].endswith(" Move to API v2.md")
    meta = frontmatter.parse((root / change["rel"]).read_text()).meta
    assert meta["status"] == "proposed" and meta["tasks"] == [f"[[{task['id']} Plan, then test]]"] * 2
    _, closed = run("note", "set", "--file", change["rel"], "--field", "status=done", vault=root)
    assert closed["changed"]["done_on"] == dt.date.today().isoformat()  # any type with done_on, not just tasks
    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}


def test_bug_investigations_and_postmortems_live_in_their_project_and_open_ones_are_mapped(run, projects_vault):
    root = projects_vault
    today = dt.date.today().isoformat()
    new = ("note", "new", "--field", "summary=s")
    run(*new, "--type", "project", "--title", "Alpha", vault=root)
    for type_name in ("debug", "incident"):
        code, out = run(*new, "--type", type_name, "--title", "Loose", vault=root)
        assert code == 2 and "project" in out["error"], type_name  # always a project's

    _, bug = run(*new, "--type", "debug", "--title", "Total ignores the discount", "--field", "project=Alpha",
                 vault=root)  # fmt: skip
    assert bug["rel"] == f"Projects/Alpha/Debug/{today} Total ignores the discount.md"
    text = (root / bug["rel"]).read_text()
    assert frontmatter.parse(text).meta["status"] == "investigating"
    assert HEADING.findall(text) == ["## Symptom", "## Repro", "## Investigation", "## Root cause", "## Fix"]
    fixed = ("--field", "project=Alpha", "--field", "status=fixed")
    run(*new, "--type", "debug", "--title", "Old crash", *fixed, vault=root)

    _, outage = run(*new, "--type", "incident", "--title", "Checkout down", "--field", "project=Alpha",
                    "--field", "date=2026-10-01", vault=root)  # fmt: skip
    assert outage["rel"] == "Projects/Alpha/Incidents/2026-10-01 Checkout down.md"  # named by the day it happened
    text = (root / outage["rel"]).read_text()
    assert frontmatter.parse(text).meta["status"] == "draft"
    assert HEADING.findall(text) == ["## Summary", "## Timeline", "## Impact", "## Root cause", "## What went well",
                                     "## Action items"]  # fmt: skip
    _, undated = run(*new, "--type", "incident", "--title", "Slow search", "--field", "project=Alpha",
                     "--field", "status=final", vault=root)  # fmt: skip
    assert undated["rel"] == f"Projects/Alpha/Incidents/{today} Slow search.md"
    code, out = run("note", "set", "--file", bug["rel"], "--field", "status=closed", vault=root)
    assert code == 2 and "status" in out["error"]

    s = schema.load(root)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}

    nodes = keyed(scene(root / draw(run, root)["rel"])[1])
    assert nodes[f"note:{today} Total ignores the discount"]["text"] == \
        f"[[{today} Total ignores the discount|Total ignores the discount]]"  # fmt: skip
    assert {"branch:Open bugs", "branch:Draft postmortems", "note:2026-10-01 Checkout down"} <= set(nodes)
    assert not {f"note:{today} Old crash", f"note:{today} Slow search"} & set(nodes)  # closed: off the map


def test_the_review_hook_prints_its_steps_and_the_core_review_may_run_each_command_in_them():
    """D151: the core review reads the hook unattended, so every synapsidian-projects command the hook
    names must be pre-approved there, and the hook can't use paths the core resolves to its own root."""
    proc = bin_run("hook", "review")
    assert proc.returncode == 0 and "synapsidian-projects progress --project" in proc.stdout
    assert "${CLAUDE_PLUGIN_ROOT}" not in proc.stdout

    review = (PROJECTS.parent / "synapsidian" / "skills" / "review" / "SKILL.md").read_text()
    allowed = frontmatter.parse(review).meta["allowed-tools"]
    assert "Bash(command -v synapsidian-projects)" in allowed and "Bash(synapsidian-projects hook *)" in allowed
    for command in set(re.findall(r"synapsidian-projects (\w[\w-]*) --", proc.stdout)):
        assert f"Bash(synapsidian-projects {command} *)" in allowed, command
    assert "`synapsidian note where` lists `synapsidian-projects`" in review  # only with the extension installed


def test_command_line_refuses_what_it_does_not_know():
    assert bin_run("extension").stdout.strip() == str(PROJECTS / "extension")
    assert bin_run("section", "Nope").returncode == 2
    assert bin_run("hook", "../etc").returncode == 2
    assert bin_run("hook", "missing").returncode == 2
    assert bin_run().returncode == 2


def test_extension_version_follows_the_plugin():
    import json

    import yaml

    plugin = json.loads((PROJECTS / ".claude-plugin/plugin.json").read_text())
    assert yaml.safe_load((PROJECTS / "extension/extension.yaml").read_text())["version"] == plugin["version"]
    assert plugin["dependencies"] == [{"name": "synapsidian", "version": "~0.33.0"}]
