from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECTS, install_projects_extension, install_work_extension
from synapsidianlib import frontmatter, obsidian_templates, schema

STUB = Path(__file__).with_name("templater_stub.mjs")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node runs the Templater stub")
HEADING = re.compile(r"^## .+$", re.MULTILINE)


@pytest.fixture
def full_vault(vault: Path) -> Path:
    """An empty vault with both add-ons' extensions installed."""
    return install_projects_extension(install_work_extension(vault))


def templater(template: str, **given: object) -> dict:
    """Run a generated template through the Templater stub: the note's text and where it moved."""
    payload = json.dumps({"template": template, **given}, default=str)
    proc = subprocess.run(["node", str(STUB)], input=payload, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert "error" not in out, out
    return out


def write_note(root: Path, rel: str, meta: dict, body: str = "") -> dict:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dump(meta, body), encoding="utf-8")
    return {"path": rel, "frontmatter": json.loads(json.dumps(meta, default=str))}


def create(root: Path, s: schema.Schema, template_rel: str, title: str, notes=(), **given: object) -> tuple[str, dict]:
    """Make a note from a generated template as a person would; returns (rel, frontmatter)."""
    template = obsidian_templates.wanted(s)[template_rel]
    answers = {"Title": title, "Summary (one sentence)": "One line."}
    out = templater(template, answers=answers, notes=list(notes), **given)
    rel = f"{out['path']}.md"
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(out["content"], encoding="utf-8")
    return rel, frontmatter.parse(out["content"]).meta


@needs_node
def test_every_generated_template_makes_a_valid_note_with_its_body_sections(full_vault):
    s = schema.load(full_vault)
    write_note(full_vault, "Projects/Web app/Web app.md", {"type": "project", "created": "2026-10-01", "summary": "s"})
    hub = {"path": "Projects/Web app/Web app.md", "frontmatter": {"type": "project"}}
    for rel_template in obsidian_templates.wanted(s):
        if not rel_template.startswith(obsidian_templates.FOLDER):
            continue
        label = Path(rel_template).stem
        rel, meta = create(full_vault, s, rel_template, f"From {label}", notes=[hub], choices={"project": "Web app"})
        assert schema.validate(meta, rel, s) == [], (label, rel, meta)
        assert "<%" not in (full_vault / rel).read_text()
        note_type = s.types[meta["type"]]
        expected = HEADING.findall(note_type.template(meta.get("kind")).read_text())
        assert HEADING.findall((full_vault / rel).read_text()) == expected, label


def test_only_types_people_create_get_a_template_and_kinds_with_a_body_get_their_own(full_vault):
    s = schema.load(full_vault)
    generated = {
        p: text for p, text in obsidian_templates.wanted(s).items() if p.startswith(f"{obsidian_templates.FOLDER}/")
    }
    # A template is no note: no Base that selects by type may list it.
    assert all(frontmatter.parse(t.split("-%>\n", 1)[1]).meta["type"] not in s.types for t in generated.values())
    names = {Path(p).stem for p in generated}
    assert {
        *("Task", "Person", "Project", "Spec", "Change", "Debug", "Incident", "Decision", "Win"),
        *("Meeting - 1-1", "Meeting - External", "Meeting - Retro"),
    } <= names
    assert {"Goal", "Note", "Note - Concept", "Note - Literature"} <= names
    # Every note kind has its own template, so the plain one asks for no kind and writes none.
    plain_note = generated["Templates/Generated/Note.md"]
    assert "\nkind:\n" in plain_note and '"name": "kind"' not in plain_note
    assert not {"Daily", "Source", "Review", "Research", "Thinking", "About", "Architecture"} & names
    assert not any(n.startswith(("Thinking", "Architecture")) for n in names)


@needs_node
def test_task_ids_continue_where_synapsidian_note_new_would(full_vault, run):
    s = schema.load(full_vault)
    task = {"type": "task", "created": "2026-10-01", "summary": "s", "status": "todo", "priority": "low"}
    notes = [
        write_note(full_vault, "Tasks/T3 One.md", {**task, "id": "T3"}),
        write_note(full_vault, "Archive/Tasks/ZAD-7 Old.md", {**task, "id": "ZAD-7"}),
    ]
    _, expected = run("note", "next-id", vault=full_vault)
    rel, meta = create(full_vault, s, "Templates/Generated/Task.md", "Water the plants", notes=notes)
    assert meta["id"] == expected["id"] == "T8"
    assert rel == "Tasks/T8 Water the plants.md"


@needs_node
def test_project_hub_and_its_notes_land_in_the_project_folder(full_vault):
    s = schema.load(full_vault)
    rel, meta = create(full_vault, s, "Templates/Generated/Project.md", "Garden", choices={"kind": "system"})
    assert rel == "Projects/Garden/Garden.md" and meta["kind"] == "system" and meta["status"] == "active"
    assert "## Links" in (full_vault / rel).read_text() and "```base" in (full_vault / rel).read_text()

    hub = {"path": rel, "frontmatter": meta}
    rel, meta = create(
        full_vault, s, "Templates/Generated/Spec.md", "Watering", notes=[hub], choices={"project": "Garden"}
    )
    assert rel == "Projects/Garden/Specs/Watering.md" and meta["project"] == "[[Garden]]"
    rel, _ = create(
        full_vault, s, "Templates/Generated/Task.md", "Buy a hose", notes=[hub], choices={"project": "Garden"}
    )
    assert rel.startswith("Projects/Garden/Tasks/T1 ")
    rel, meta = create(full_vault, s, "Templates/Generated/Task.md", "Loose end", notes=[hub], choices={"project": ""})
    assert rel == "Tasks/T1 Loose end.md" and meta["project"] is None


@needs_node
def test_decision_number_matches_synapsidian_projects_decision_number(full_vault):
    s = schema.load(full_vault)
    decision = {"type": "decision", "created": "2026-10-01", "summary": "s", "status": "accepted"}

    def numbered(rel: str, project: str, number: int) -> dict:
        return write_note(full_vault, rel, {**decision, "project": f"[[{project}]]", "number": number})

    notes = [
        {"path": "Projects/Garden/Garden.md", "frontmatter": {"type": "project"}},
        numbered("Projects/Garden/Decisions/2026-10-01 A.md", "Garden", 2),
        numbered("Archive/Projects/Garden/Decisions/2026-09-01 B.md", "Garden", 4),  # archived ones count
        numbered("Projects/Other/Decisions/2026-10-02 C.md", "Other", 9),
    ]
    query = {"notes": [{"type": "decision", **n["frontmatter"]} for n in notes[1:]]}
    expected = subprocess.run(
        [sys.executable, str(PROJECTS / "scripts" / "projects.py"), "decision-number", "--project", "Garden"],
        input=json.dumps(query), capture_output=True, text=True, check=True,
    )  # fmt: skip
    template = "Templates/Generated/Decision.md"
    rel, meta = create(full_vault, s, template, "Use drip", notes=notes, choices={"project": "Garden"})
    assert meta["number"] == json.loads(expected.stdout)["number"] == 5
    assert rel == "Projects/Garden/Decisions/2026-10-28 Use drip.md"
    _, meta = create(full_vault, s, template, "Loose", notes=notes, choices={"project": ""})
    assert meta["number"] is None  # a decision outside a project has no number


def test_sync_rewrites_only_what_synapsidian_wrote_and_removes_what_it_no_longer_ships(vault):
    s = schema.load(vault)
    first = obsidian_templates.sync(vault, s)
    task = vault / "Templates/Generated/Task.md"
    assert "Templates/Generated/Task.md" in first.created and "Templates/Daily.md" in first.created
    assert obsidian_templates.sync(vault, s) == obsidian_templates.Synced()  # idempotent

    record = json.loads((vault / obsidian_templates.RECORD).read_text())
    task.write_text("an older version synapsidian wrote")
    record["Templates/Generated/Task.md"] = obsidian_templates.digest("an older version synapsidian wrote")
    record["Templates/Generated/Gone.md"] = obsidian_templates.digest("old")
    (vault / "Templates/Generated/Gone.md").write_text("old")
    (vault / obsidian_templates.RECORD).write_text(json.dumps(record))
    (vault / "Templates/Generated/Person.md").write_text("mine now")

    again = obsidian_templates.sync(vault, s)
    assert "Templates/Generated/Task.md" in again.updated and task.read_text().startswith("<%*")
    assert again.removed == ["Templates/Generated/Gone.md"] and not (vault / "Templates/Generated/Gone.md").exists()
    assert any(k.startswith("Templates/Generated/Person.md") for k in again.kept)
    assert (vault / "Templates/Generated/Person.md").read_text() == "mine now"


def test_an_older_vaults_unchanged_daily_template_is_adopted_and_an_edited_one_kept(vault):
    s = schema.load(vault)
    (vault / "Templates").mkdir()
    (vault / "Templates/Daily.md").write_text(obsidian_templates.daily(s))
    assert "Templates/Daily.md" not in obsidian_templates.sync(vault, s).kept
    assert "Templates/Daily.md" in json.loads((vault / obsidian_templates.RECORD).read_text())

    other = vault / "Other"
    (other / "Templates").mkdir(parents=True)
    (other / "Templates/Daily.md").write_text("my own daily")
    result = obsidian_templates.sync(other, s)
    assert any(k.startswith("Templates/Daily.md") for k in result.kept)
    assert (other / "Templates/Daily.md").read_text() == "my own daily"
