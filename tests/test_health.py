from __future__ import annotations

import re
import subprocess
from pathlib import Path

from synapsidianlib import frontmatter

PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


def note(vault: Path, rel: str, text: str) -> Path:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def commit_all(vault: Path) -> None:
    subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(vault), "commit", "-qm", "seed", "--date", "2026-10-01T10:00:00"],
        check=True,
        env={"GIT_COMMITTER_DATE": "2026-10-01T10:00:00", "PATH": "/usr/bin:/bin"},
    )


def seed(vault: Path) -> None:
    note(
        vault,
        "Notes/Export format.md",
        "---\ntype: note\ncreated: 2026-10-01\nsummary: s\ntags:\n- Pay_Equity\n- '#exports'\n---\n"
        "See [[pay gap]] and [[Nowhere]].\n\nExample: `[[pay gap]]` and `[[create a link]]`.\n\n"
        "```markdown\n[[Also not a link]]\n```\n",
    )
    note(vault, "Notes/Pay gap.md", "---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\nBody\n")
    note(vault, "Notes/Lonely.md", "---\ntype: note\nsummary: nobody links here\n---\n")
    note(
        vault,
        "Tasks/T1 Late.md",
        "---\ntype: task\ncreated: 2026-10-01\nsummary: s\nid: T1\nstatus: todo\npriority: high\n"
        "due: 2026-10-05\n---\n",
    )
    note(vault, "Inbox/2026-10-01 0900 old.md", "---\ntype: capture\ncreated: 2026-10-01\n---\nold thought\n")
    note(vault, "Archive/Notes/Ignored.md", "no frontmatter at all")


def test_report_only_changes_nothing(run, vault):
    seed(vault)
    before = {p: p.read_text() for p in vault.rglob("*.md")}
    code, out = run("health", "--today", "2026-10-14", vault=vault)
    assert code == 0 and out["fixed"] == []
    assert {p: p.read_text() for p in vault.rglob("*.md")} == before
    counts = out["counts"]
    assert counts["broken_links"] == 1 and out["issues"]["broken_links"][0]["link"] == "Nowhere"
    assert out["issues"]["link_case"] == [{"rel": "Notes/Export format.md", "link": "pay gap", "should_be": "Pay gap"}]
    assert out["issues"]["tag_format"][0]["should_be"] == ["pay-equity", "exports"]
    assert {o["rel"] for o in out["issues"]["orphans"]} == {"Notes/Export format.md", "Notes/Lonely.md"}
    assert out["issues"]["overdue_tasks"] == [{"rel": "Tasks/T1 Late.md", "due": "2026-10-05"}]
    assert out["issues"]["stale_inbox"][0]["rel"].startswith("Inbox/")
    assert all("Archive" not in str(v) for v in out["issues"].values())


def test_templater_commands_left_in_notes_are_reported_but_not_in_code_or_templates(run, vault):
    note(vault, "Notes/Raw.md", '---\ntype: note\ncreated: <% tp.date.now("YYYY-MM-DD") %>\nsummary: s\n---\n')
    note(
        vault,
        "Notes/Docs.md",
        "---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\nUse `<% tp.file.title %>`.\n\n"
        "```js\n<%* tR += 'x' %>\n```\n",
    )
    note(vault, "Templates/Generated/Note.md", "---\ntype: note\ncreated: <% v.created %>\n---\n")
    _, out = run("health", "--today", "2026-10-14", vault=vault)
    assert out["issues"]["templater_leftovers"] == [
        {"rel": "Notes/Raw.md", "commands": ['<% tp.date.now("YYYY-MM-DD") %>']}
    ]


def test_fix_applies_only_the_safe_fixes(run, vault):
    seed(vault)
    commit_all(vault)
    lonely = vault / "Notes/Lonely.md"
    code, out = run("health", "--fix", "--today", "2026-10-14", vault=vault)
    assert code == 0
    assert {f["rel"] for f in out["fixed"]} == {"Notes/Export format.md", "Notes/Lonely.md"}

    export = frontmatter.parse((vault / "Notes/Export format.md").read_text())
    assert export.meta["tags"] == ["pay-equity", "exports"]
    assert "[[Pay gap]]" in export.body and "[[Nowhere]]" in export.body  # broken link left for a person
    assert "`[[pay gap]]`" in export.body  # code is shown as text, never rewritten
    assert str(frontmatter.parse(lonely.read_text()).meta["created"]) == "2026-10-01"  # from the first commit
    assert (vault / "Archive/Notes/Ignored.md").read_text() == "no frontmatter at all"
    assert "T1" in (vault / "Tasks/T1 Late.md").read_text()  # overdue is reported, never changed

    _, again = run("health", "--fix", "--today", "2026-10-14", vault=vault)
    assert again["fixed"] == []  # idempotent


def test_fix_leaves_untyped_and_non_utf8_notes_alone_and_keeps_hashed_blocks_intact(run, vault):
    """D121: `type: null` on untyped notes, U+FFFD over Latin-2 text, and a link-case fix that
    made a hashed block read as hand-edited."""
    from synapsidianlib import blocks

    untyped = note(vault, "Notes/Recipe.md", "---\naliases: [Recipe]\n---\nSoup.\n")
    latin2 = vault / "Notes" / "Stara.md"
    latin2.write_bytes(
        "---\ntype: note\ncreated: 2026-10-01\nsummary: s\ntags:\n- Pay_Equity\n---\nżółw\n".encode("iso-8859-2")
    )
    note(vault, "Notes/Garden.md", "---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\nx\n")
    inner = "- see [[garden]]\n"
    hashed = note(
        vault,
        "Notes/Plan.md",
        f"---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\n<!-- @generated:facts sha={blocks.digest(inner)} -->\n"
        f"{inner}<!-- @end -->\n",
    )
    commit_all(vault)
    before_untyped, before_latin2 = untyped.read_bytes(), latin2.read_bytes()
    _, out = run("health", "--fix", "--today", "2026-10-14", vault=vault)
    assert untyped.read_bytes() == before_untyped
    assert latin2.read_bytes() == before_latin2 and {"rel": "Notes/Stara.md"} in out["issues"]["not_utf8"]
    text = hashed.read_text()
    assert "[[Garden]]" in text
    assert all(m.group(2) == blocks.digest(m.group(3)) for m in blocks.ANY_BLOCK.finditer(text))


def test_a_missing_note_several_notes_link_to_is_wanted_not_broken(run, vault):
    """D126: unresolved links grouped by target; two or more sources make a wanted note."""
    head = "---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\n"
    note(vault, "Notes/A.md", head + "See [[Spaced repetition]] and [[Typo here]].\n")
    note(vault, "Notes/B.md", head + "Also [[spaced repetition|SR]].\n")
    _, out = run("health", "--today", "2026-10-14", vault=vault)
    assert out["issues"]["wanted_notes"] == [{"link": "Spaced repetition", "linked_from": ["Notes/A.md", "Notes/B.md"]}]
    assert out["issues"]["broken_links"] == [{"rel": "Notes/A.md", "link": "Typo here"}]


def test_templater_code_in_sources_and_broken_blocks_are_reported(run, vault):
    note(vault, "Sources/Page.md", "---\ntype: source\ncreated: 2026-10-01\n---\nHi <%* app.vault.delete() %>\n")
    note(
        vault,
        "Notes/Day.md",
        "---\ntype: note\ncreated: 2026-10-01\nsummary: s\n---\n<!-- @generated:x -->\nlost end\n",
    )
    _, out = run("health", "--today", "2026-10-14", vault=vault)
    assert any(i["rel"] == "Sources/Page.md" for i in out["issues"]["templater_leftovers"])
    assert out["issues"]["broken_blocks"] == [{"rel": "Notes/Day.md", "blocks": ["x"]}]


def test_orphans_come_with_link_proposals_and_nothing_is_linked(run, vault):
    head = "---\ntype: {type}\ncreated: 2026-10-01\nsummary: s\ntags:\n- payroll\n---\n"
    note(vault, "Notes/Payroll export.md", head.format(type="note") + "Body\n")
    note(
        vault,
        "Notes/Release checklist.md",
        head.format(type="note") + "The payroll export runs on Friday.\n\n`Release checklist` in code is no mention.\n",
    )
    note(vault, "Notes/Tag buddy.md", head.format(type="note") + "Nothing relevant.\n")
    note(
        vault,
        "Daily/2026-10-02.md",
        head.format(type="daily") + "<!-- @generated:devlog -->\n- Updated the Release checklist.\n<!-- @end -->\n",
    )
    note(
        vault,
        "Notes/Ops.md",
        head.format(type="note").replace("payroll", "misc") + "Ops are mentioned everywhere: ops.\n",
    )
    before = {p: p.read_text() for p in vault.rglob("*.md")}

    _, out = run("health", "--fix", "--today", "2026-10-14", vault=vault)

    orphans = {o["rel"]: o for o in out["issues"]["orphans"]}
    assert orphans["Notes/Payroll export.md"] == {
        "rel": "Notes/Payroll export.md",
        "mentioned_in": ["Notes/Release checklist.md"],
        "related": ["Notes/Tag buddy.md"],
    }
    assert orphans["Notes/Release checklist.md"]["related"] == ["Notes/Payroll export.md", "Notes/Tag buddy.md"]
    assert "mentioned_in" not in orphans["Notes/Release checklist.md"]  # a generated daily block and code don't count
    assert orphans["Notes/Ops.md"] == {"rel": "Notes/Ops.md"}  # too short a title to match prose
    assert {p: p.read_text() for p in vault.rglob("*.md")} == before  # proposals only


def test_a_link_from_a_daily_review_or_capture_note_does_not_make_a_note_reachable(run, vault):
    head = "---\ntype: {type}\ncreated: 2026-10-01\nsummary: s\n---\n"
    for title in ("Logged", "Reviewed", "Captured", "Linked"):
        note(vault, f"Notes/{title}.md", head.format(type="note") + "Body\n")
    note(vault, "Daily/2026-10-02.md", head.format(type="daily") + "Wrote [[Logged]] and [[Missing]].\n")
    note(vault, "Reviews/2026-W40.md", head.format(type="review") + "See [[Reviewed]].\n")
    note(vault, "Inbox/2026-10-02 0900 thought.md", head.format(type="capture") + "About [[Captured]].\n")
    note(vault, "Tasks/T1 Do it.md", head.format(type="task") + "For [[Linked]].\n")

    _, out = run("health", "--today", "2026-10-03", vault=vault)

    assert {o["rel"] for o in out["issues"]["orphans"]} == {
        "Notes/Logged.md",
        "Notes/Reviewed.md",
        "Notes/Captured.md",
    }
    # Such a note's links are still checked.
    assert out["issues"]["broken_links"] == [{"rel": "Daily/2026-10-02.md", "link": "Missing"}]


def test_tasks_stuck_in_doing_or_waiting_are_reported_by_last_commit(run, vault):
    task = "---\ntype: task\ncreated: 2026-10-01\nsummary: s\nid: {id}\nstatus: {status}\npriority: low\n{extra}---\n"
    note(vault, "Tasks/T2 Stalled.md", task.format(id="T2", status="doing", extra=""))
    note(vault, "Tasks/T3 Touched.md", task.format(id="T3", status="waiting", extra=""))
    note(vault, "Tasks/T4 Late.md", task.format(id="T4", status="doing", extra="due: 2026-10-05\n"))
    note(vault, "Tasks/T5 Queued.md", task.format(id="T5", status="todo", extra=""))
    commit_all(vault)  # every file now has a fresh mtime, but its last commit is 2026-10-01
    touched = vault / "Tasks/T3 Touched.md"
    touched.write_text(touched.read_text() + "Waiting on Alex's answer.\n")  # uncommitted edit counts as a change

    _, out = run("health", "--today", "2026-10-20", vault=vault)

    assert out["issues"]["stuck_tasks"] == [
        {"rel": "Tasks/T2 Stalled.md", "status": "doing", "unchanged_since": "2026-10-01"}
    ]
    assert [t["rel"] for t in out["issues"]["overdue_tasks"]] == ["Tasks/T4 Late.md"]  # reported once, as overdue


def test_tasks_in_project_folders_are_dated_by_their_own_commits(run, projects_vault):
    vault = projects_vault
    task = "---\ntype: task\ncreated: 2026-10-01\nsummary: s\nid: {id}\nstatus: doing\npriority: low\n" \
           "project: '[[Alpha]]'\n---\n"  # fmt: skip
    note(vault, "Projects/Alpha/Tasks/T7 Nested.md", task.format(id="T7"))
    note(vault, "Projects/Alpha/Tasks/T8 Fresh.md", task.format(id="T8"))
    commit_all(vault)
    fresh = vault / "Projects/Alpha/Tasks/T8 Fresh.md"
    fresh.write_text(fresh.read_text() + "Moving again.\n")

    _, out = run("health", "--today", "2026-10-20", vault=vault)

    assert out["issues"]["stuck_tasks"] == [
        {"rel": "Projects/Alpha/Tasks/T7 Nested.md", "status": "doing", "unchanged_since": "2026-10-01"}
    ]
    assert "schema" not in out["issues"]


def test_skill_references_exist():
    """Every ${CLAUDE_PLUGIN_ROOT}/references/... a skill points at must ship with the plugin."""
    for skill in PLUGINS.glob("*/skills/*/SKILL.md"):
        root = skill.parents[2]
        for ref in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+\.(?:md|yaml))", skill.read_text()):
            assert (root / ref).is_file(), f"{skill.parent.name} -> {ref}"


def test_every_skill_has_a_description_and_balanced_fences():
    for skill in PLUGINS.glob("*/skills/*/SKILL.md"):
        text = skill.read_text()
        meta = frontmatter.parse(text).meta
        assert meta and meta.get("name") == skill.parent.name and len(meta.get("description", "")) > 80, skill
        assert text.count("```") % 2 == 0, skill
