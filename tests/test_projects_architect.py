from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from block import EditedBlock, check_blocks, read_block, replace_block
from conftest import PROJECTS
from synapsidianlib import schema, vault

ARCHITECT = PROJECTS / "scripts" / "architect.py"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def architect(*args: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(ARCHITECT), *args], capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "monorepo"
    write(root, "web/package.json", json.dumps({
        "name": "web", "dependencies": {"vue": "3.5.43", "pinia": "4.0.3", "left-pad": "1.0.0"},
        "devDependencies": {"vitest": "5.0.3"}, "scripts": {"dev": "vite", "test": "vitest"},
    }))  # fmt: skip
    write(root, "web/src/main.ts", "import { createApp } from 'vue'\n")
    write(root, "web/src/router/index.ts", (
        "export const routes = [\n"
        "  { path: '/reports/:id', name: 'Report', component: () => import('@/pages/ReportPage.vue') },\n"
        "  { path: '/login', name: 'Login', component: LoginPage },\n]\n"
    ))  # fmt: skip
    write(root, "web/src/router/index.spec.ts", "path: '/not-a-route'\n")
    write(root, "web/src/domains/report/Report.vue", "import { useUser } from '@/domains/user/useUser'\n")
    write(root, "web/src/domains/report/store.ts", "export const useReport = defineStore('report', {})\n")
    test_code = "defineStore('mock-only', {})\nimport x from '@/domains/chart/x'\n"  # must not count
    write(root, "web/src/domains/report/Report.spec.ts", test_code)
    write(root, "web/src/domains/report/Report.story.vue", test_code)
    write(root, "web/src/domains/user/useUser.ts", "export const useUser = defineStore('user', {})\n")
    write(root, "web/node_modules/x/index.js", "ignored\n")
    write(root, "svc/pyproject.toml", '[project]\nname = "svc"\nversion = "1.0"\ndependencies = ["httpx"]\n'
                                      '[project.scripts]\nsvc = "svc.cli:main"\n')  # fmt: skip
    write(root, "svc/svc/__main__.py", "from svc.cli import main\nmain()\n")
    write(root, "svc/bin/svc", "#!/bin/sh\nexec python -m svc\n")
    write(root, "svc/svc/billing/invoices.py", "def total():\n    return 1\n")
    write(root, "svc/svc/billing/tax.py", "RATE = 1\n")
    write(root, "svc/svc/users/models.py", "class User: ...\n")
    write(root, "svc/tests/test_billing.py", "def test_total(): ...\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git(root, "-c", "user.name=T", "-c", "user.email=t@e.st", "add", "-A")
    git(root, "-c", "user.name=T", "-c", "user.email=t@e.st", "commit", "-qm", "init")
    return root


def test_apps_lists_every_folder_with_a_manifest_and_its_profile(repo):
    code, out = architect("apps", "--repo", str(repo))
    assert code == 0 and out["apps"] == [
        {"app": "svc", "path": "svc", "manifest": "pyproject.toml", "profile": "generic"},
        {"app": "web", "path": "web", "manifest": "package.json", "profile": "vue"},
    ]


def test_vue_scan_keeps_domains_stores_and_routes_without_touching_the_repo(repo):
    first = git(repo, "rev-parse", "HEAD")
    code, out = architect("scan", "--repo", str(repo), "--app", "web")
    assert code == 0 and out["commit"] == first and out["path"] == "web" and out["profile"] == "vue"
    assert out["package"]["dependencies"] == {"vue": "3.5.43", "pinia": "4.0.3"}
    assert out["package"]["tooling"] == {"vitest": "5.0.3"} and out["package"]["scripts"] == ["dev", "test"]
    assert out["source_root"] == "src/domains"
    report = next(m for m in out["modules"] if m["name"] == "report")
    assert report["files"] == 2 and report["test_files"] == 2
    assert report["stores"] == ["report"] and report["depends_on"] == {"user": 1}
    user = next(m for m in out["modules"] if m["name"] == "user")
    assert user["used_by_modules"] == 1 and out["stores"] == ["report", "user"]
    assert [(r["path"], r["name"], r["component"]) for r in out["routes"]] == [
        ("/reports/:id", "Report", "@/pages/ReportPage.vue"),
        ("/login", "Login", "LoginPage"),
    ]
    assert "src/main.ts" in out["entry_points"]
    assert all("node_modules" not in f["file"] and ".spec." not in f["file"] for f in out["largest"])
    assert git(repo, "status", "--porcelain") == ""  # read-only

    write(repo, "web/src/domains/user/useUser.ts", "export const useUser = defineStore('user2', {})\n")
    write(repo, "web/src/main.ts", "// changed\n")
    git(repo, "-c", "user.name=T", "-c", "user.email=t@e.st", "commit", "-qam", "change")
    _, again = architect("scan", "--repo", str(repo), "--app", "web", "--since", first)
    assert again["changed"]["files"] == 2
    by_module = again["changed"]["by_module"]
    assert by_module == {"user": ["src/domains/user/useUser.ts"], "(outside modules)": ["src/main.ts"]}


def test_generic_scan_finds_the_package_its_modules_and_entry_points(repo):
    code, out = architect("scan", "--repo", str(repo / "svc"), "--app", ".")
    assert code == 0 and out["app"] == "svc" and out["path"] == "svc" and out["profile"] == "generic"
    assert out["source_root"] == "svc"  # the Python package named in pyproject.toml
    assert {m["name"]: m["files"] for m in out["modules"]} == {"billing": 2, "users": 1}
    assert out["test_files"] == 1 and out["manifests"][0]["dependencies"] == ["httpx"]
    assert {"svc/__main__.py", "bin/svc", "pyproject script: svc"} <= set(out["entry_points"])


def test_scan_refuses_what_it_cannot_read(repo, tmp_path):
    assert architect("scan", "--repo", str(repo), "--app", "nope")[0] == 2
    assert architect("scan", "--repo", str(repo), "--app", "../..")[0] == 2  # never outside the repository
    code, out = architect("apps", "--repo", "https://example.com/x.git")
    assert code == 2 and "local clone" in out["error"]
    (tmp_path / "plain").mkdir()
    assert architect("apps", "--repo", str(tmp_path / "plain"))[0] == 2


OLD_WORK_SCHEMA = """types:
  architecture:
    folder: Architecture
    filename: "{app} {title}"
    fields:
      app: {required: true, kind: text}
      kind: {required: true, kind: text, enum: [overview, domain]}
      path: {kind: text}
      scanned_commit: {required: true, kind: text}
      scanned_at: {required: true, kind: date}
"""
OLD_NOTE = """---
type: architecture
created: 2026-10-14
summary: The web app
app: web
kind: overview
path: web
scanned_commit: abc1234
scanned_at: 2026-10-14
---
## Summary
<!-- @generated:summary sha=000000000000 -->
x
<!-- @end -->
"""


def test_architecture_moves_from_synapsidian_work_to_projects_without_breaking_the_vault(run, vault_with_old_work):
    root = vault_with_old_work
    s = schema.load(root)  # old synapsidian-work and new synapsidian-projects both define the type: a warning, no error
    assert any("'architecture' is also defined by synapsidian-projects" in w for w in s.warnings)
    assert "project" in s.types["architecture"].fields  # synapsidian-projects' definition wins (name order)
    _, check = run("setup", "check", "--vault", str(root))
    assert check["schema_warnings"]

    _, unlinked = run("query", "notes", "--type", "architecture", "--where", "project=", vault=root)
    assert [n["rel"] for n in unlinked["notes"]] == ["Architecture/web Overview.md"]
    run("note", "new", "--type", "project", "--title", "web", "--field", "kind=repository",
        "--field", "summary=s", vault=root)  # fmt: skip
    code, moved = run("note", "set", "--file", "Architecture/web Overview.md", "--field", "project=web", vault=root)
    assert code == 0 and moved["rel"] == "Projects/web/Architecture/web Overview.md", moved
    assert moved["from"] == "Architecture/web Overview.md"
    problems = {n.rel: schema.validate(n.meta, n.rel, schema.load(root)) for n in vault.iter_notes(root)}
    assert {rel: p for rel, p in problems.items() if p} == {}

    code, made = run("note", "new", "--type", "architecture", "--title", "Overview", "--field", "app=api",
                     "--field", "kind=overview", "--field", "scanned_commit=abc1234",
                     "--field", "scanned_at=2026-10-28", "--field", "summary=s", vault=root)  # fmt: skip
    assert code == 2 and "project" in made["error"]  # a new architecture note always has a project


@pytest.fixture
def vault_with_old_work(projects_vault: Path) -> Path:
    old = projects_vault / ".synapsidian/extensions/synapsidian-work"
    old.mkdir(parents=True)
    (old / "extension.yaml").write_text("name: synapsidian-work\nversion: 0.2.1\n")
    (old / "schema.yaml").write_text(OLD_WORK_SCHEMA)
    write(projects_vault, "Architecture/web Overview.md", OLD_NOTE)
    return projects_vault


NOTE = "## Structure\n<!-- @generated:structure -->\nold\n<!-- @end -->\n\n## Notes\nmine\n"


def test_hashed_block_detects_hand_edits():
    text = replace_block(NOTE, "structure", "generated v1", hashed=True)
    assert "<!-- @generated:structure sha=" in text and read_block(text, "structure") == "generated v1\n"
    assert check_blocks(text) == [{"name": "structure", "status": "ok"}]

    text2 = replace_block(text, "structure", "generated v2")  # stays hashed without --hash
    assert "sha=" in text2 and text2.endswith("## Notes\nmine\n")

    edited = text2.replace("generated v2", "generated v2 plus my remark")
    assert check_blocks(edited) == [{"name": "structure", "status": "edited"}]
    with pytest.raises(EditedBlock) as caught:
        replace_block(edited, "structure", "generated v3")
    assert "my remark" in caught.value.current
    forced = replace_block(edited, "structure", "generated v3", force=True)
    assert check_blocks(forced) == [{"name": "structure", "status": "ok"}]


def test_unhashed_blocks_behave_as_before():
    text = replace_block(NOTE, "structure", "new")
    assert text == NOTE.replace("old", "new")
    assert check_blocks(text) == [{"name": "structure", "status": "unhashed"}]
