from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapsidianlib import frontmatter


def hook_input(tool: str, path: Path) -> str:
    return json.dumps({"tool_name": tool, "tool_input": {"file_path": str(path)}})


def test_brief_lists_overdue_due_and_projects(run, fixture_vault):
    code, out = run("brief", "--plain", "--today", "2026-10-16", vault=fixture_vault)
    assert code == 0
    assert "### Overdue\n- [[T1 Review export TDD]] (high, due 2026-10-15, 1d overdue" in out
    assert "### In progress\n- [[T2 Migrate filter panel]]" in out
    assert "[[Onboarding revamp]]" not in out  # paused projects stay out
    assert "[[T4 " not in out  # done tasks stay out
    assert "role: Senior frontend engineer" in out
    assert "Frontend engineer working on the pay equity analytics product." in out
    assert "## Who I am" not in out  # template headings stay out of the brief
    assert len(out) <= 6000


def test_brief_says_a_task_is_blocked_while_what_it_waits_on_is_open(run, vault):
    new = ("note", "new", "--type", "task", "--field", "summary=s")
    _, paint = run(*new, "--title", "Buy the paint", vault=vault)
    _, tape = run(*new, "--title", "Tape the edges", "--field", "status=done", vault=vault)
    blockers = f"blocked_by=[[{paint['id']} Buy the paint]],[[{tape['id']} Tape the edges]]"
    code, room = run(*new, "--title", "Paint the room", "--field", "status=doing", "--field", blockers, vault=vault)
    assert code == 0

    _, out = run("brief", "--plain", vault=vault)
    assert f"- [[{room['id']} Paint the room]] (medium, doing, blocked by {paint['id']} Buy the paint)" in out

    run("note", "set", "--file", paint["rel"], "--field", "status=done", vault=vault)
    _, out = run("brief", "--plain", vault=vault)
    assert f"- [[{room['id']} Paint the room]] (medium, doing)" in out  # both done: free to start


def test_brief_speaks_of_projects_only_when_the_schema_has_them(fixture_vault, monkeypatch):
    import dataclasses
    import datetime as dt

    import brief
    from synapsidianlib import schema

    full = schema.load(fixture_vault)
    with_projects = brief.build(fixture_vault, dt.date(2026, 10, 16), minimal=False)
    assert "### Active projects" in with_projects

    task = full.types["task"]
    without = dataclasses.replace(
        full,
        types={
            **{k: v for k, v in full.types.items() if k != "project"},
            "task": dataclasses.replace(task, fields={k: f for k, f in task.fields.items() if k != "project"}),
        },
    )
    monkeypatch.setattr(brief.schema, "load", lambda _root: without)
    plain = brief.build(fixture_vault, dt.date(2026, 10, 16), minimal=False)
    assert "### Active projects" not in plain
    assert "[[T1 Review export TDD]] (high, due 2026-10-15, 1d overdue)" in plain  # no project after the task


RULES_ABOUT = """---
type: about
role: Engineer
protected:
  - Personal
  - Journal/Private.md
---
## Who I am
I build things.

## Rules
<!-- Your rules for Claude. For example:
- an example that must stay out
-->
- Never file notes about my family.
- Keep book notes in the language of the book.

## How I work
Mornings only.
"""


def test_brief_carries_the_vault_rules_whole_even_after_compaction(run, fixture_vault):
    (fixture_vault / "About.md").write_text(RULES_ABOUT)
    for args in (("--plain", "--today", "2026-10-16"), ("--plain", "--minimal")):
        _, out = run("brief", *args, vault=fixture_vault)
        about, rules = out.split("### Vault rules", 1)
        assert "I build things." in about or "--minimal" in args
        assert "Never file notes" not in about and "protected" not in about
        assert "- Never file notes about my family.\n- Keep book notes in the language of the book." in rules
        assert "`Personal`, `Journal/Private.md`" in rules
        assert "example that must stay out" not in out and "<!--" not in out
    _, full = run("brief", "--plain", "--today", "2026-10-16", vault=fixture_vault)
    assert "Mornings only." in full  # sections after Rules still reach the About text
    assert full.index("### Vault rules") < full.index("### Today")  # before the part the length cap cuts


def test_brief_without_rules_has_no_rules_block(run, fixture_vault):
    _, out = run("brief", "--plain", "--today", "2026-10-16", vault=fixture_vault)
    assert "Vault rules" not in out


def test_brief_exports_the_vault_for_bash_commands(run, fixture_vault, tmp_path):
    env_file = tmp_path / "claude-env.sh"
    run("brief", vault=fixture_vault, env={"CLAUDE_ENV_FILE": str(env_file)})
    assert env_file.read_text() == f"export SYNAPSIDIAN_VAULT={fixture_vault}\n"


def test_brief_hook_json_minimal_and_silent_without_vault(run, fixture_vault, tmp_path):
    _, payload = run("brief", "--minimal", vault=fixture_vault)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Overdue" not in context and len(context) < 1000
    assert run("brief", vault=tmp_path / "missing") == (0, None)
    assert run("brief") == (0, None)


def test_brief_json_is_the_same_agenda_as_data(run, fixture_vault, tmp_path):
    code, out = run("brief", "--json", "--today", "2026-10-16", vault=fixture_vault)
    assert code == 0 and out["ok"] is True and out["today"] == "2026-10-16"
    sections = {s["key"]: s["tasks"] for s in out["sections"]}
    assert list(sections) == ["overdue", "today", "doing", "upcoming"]
    overdue = sections["overdue"][0]
    assert overdue["id"] == "T1" and overdue["days"] == -1 and overdue["priority"] == "high"
    assert overdue["rel"].endswith("T1 Review export TDD.md")
    assert overdue["summary"] and "\n" not in overdue["summary"]
    assert sections["doing"][0]["title"] == "T2 Migrate filter panel"
    assert all(t["status"] != "done" for t in out["open"])
    assert run("brief", "--json", vault=tmp_path / "missing")[1]["ok"] is False


def test_validate_hook_warns_only_for_bad_vault_notes(run, fixture_vault, tmp_path):
    good = fixture_vault / "Notes" / "Feature flags.md"
    assert run("validate", "--hook", stdin=hook_input("Write", good), vault=fixture_vault) == (0, None)

    bad = fixture_vault / "Notes" / "Bad.md"
    bad.write_text("---\ntype: note\n---\nx")
    code, payload = run("validate", "--hook", stdin=hook_input("Write", bad), vault=fixture_vault)
    assert code == 0
    assert "`summary` is required" in payload["hookSpecificOutput"]["additionalContext"]
    assert "decision" not in payload  # never blocks

    outside = tmp_path / "elsewhere.md"
    outside.write_text("no frontmatter")
    assert run("validate", "--hook", stdin=hook_input("Write", outside), vault=fixture_vault) == (0, None)
    assert run("validate", "--hook", stdin="not json", vault=fixture_vault) == (0, None)


def test_validate_flags_credentials_in_a_note(run, fixture_vault):
    note = fixture_vault / "Notes" / "Feature flags.md"
    note.write_text(note.read_text() + "\ntoken ghp_" + "a" * 36 + "\n")
    _, payload = run("validate", "--hook", stdin=hook_input("Edit", note), vault=fixture_vault)
    assert "looks like a GitHub token" in payload["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize(
    "secret",
    [
        "AIza" + "B" * 35,
        "sk_live_" + "c" * 24,
        "npm_" + "d" * 36,
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
        "https://hooks.slack.com/services/T00000000/B00000000/" + "e" * 24,
    ],
)
def test_note_new_refuses_a_credential(run, vault, secret):
    rc, out = run(
        "note",
        "new",
        "--type",
        "idea",
        "--title",
        "Keys",
        "--field",
        "summary=s",
        "--body-file",
        "-",
        vault=vault,
        stdin=f"the key is {secret}\n",
    )
    assert rc == 2 and "credential" in out["error"]
    assert not (vault / "Ideas").exists()


def test_a_prompt_starting_with_two_chevrons_is_captured_without_reaching_claude(vault, tmp_path):
    """D137: UserPromptSubmit writes `>> text` to Inbox/, commits it and blocks the prompt."""
    import os
    import subprocess

    hook = Path(__file__).resolve().parents[1] / "plugins" / "synapsidian" / "hooks" / "capture.sh"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN", "SYNAPSIDIAN_"))}
    env |= {"SYNAPSIDIAN_VAULT": str(vault), "SYNAPSIDIAN_SETTINGS_FILE": str(tmp_path / "none.json")}

    def submit(prompt: str) -> dict | None:
        payload = json.dumps({"session_id": "s", "hook_event_name": "UserPromptSubmit", "prompt": prompt})
        out = subprocess.run(["/bin/sh", str(hook)], input=payload, text=True, capture_output=True, env=env)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout) if out.stdout.strip() else None

    assert submit("fix the failing test") is None  # an ordinary prompt: no output, no uv
    assert submit("compare a >> b") is None
    out = submit(">> Ask Alex about the garden budget https://example.com/plan")
    assert out["decision"] == "block" and out["hookSpecificOutput"]["suppressOriginalPrompt"] is True
    [note] = list((vault / "Inbox").glob("*.md"))
    assert note.name.endswith(" Ask Alex about the garden budget.md")
    meta = frontmatter.parse(note.read_text()).meta
    assert meta["type"] == "capture" and meta["source_url"] == "https://example.com/plan"
    log = subprocess.run(["git", "-C", str(vault), "log", "--format=%s"], capture_output=True, text=True).stdout
    assert log.startswith("synapsidian(capture): ")
    refused = submit(">> my token ghp_" + "a" * 36)
    assert refused["decision"] == "block" and "not captured" in refused["reason"]
    assert len(list((vault / "Inbox").glob("*.md"))) == 1


def test_validate_all_on_fixture_is_clean(run, fixture_vault):
    code, result = run("validate", "--all", vault=fixture_vault)
    assert code == 0 and result["ok"] and result["checked"] == 30


def test_approve_allows_vault_notes_only(run, vault, tmp_path):
    def decision(tool: str, path: Path, **env: str):
        _, out = run("approve", stdin=hook_input(tool, path), vault=vault, env=env)
        return out["hookSpecificOutput"]["permissionDecision"] if out else None

    assert decision("Write", vault / "Notes" / "x.md") == "allow"
    assert decision("Edit", vault / "Bases" / "Tasks.base") == "allow"
    assert decision("Write", vault / ".git" / "config") is None
    assert decision("Write", vault / ".obsidian" / "app.json") is None
    assert decision("Write", vault / "script.sh") is None
    assert decision("Write", tmp_path / "outside.md") is None
    assert decision("Write", vault / "Notes" / ".." / ".." / "escape.md") is None
    assert decision("Bash", vault / "Notes" / "x.md") is None
    assert decision("Write", vault / "Notes" / "x.md", CLAUDE_PLUGIN_OPTION_AUTO_APPROVE_VAULT_EDITS="false") is None

    # macOS: the hook sees whatever case Claude typed; the folder on disk is "Synapsidian".
    other_case = Path(str(vault).replace("/Synapsidian", "/synapsidian")) / "Notes" / "x.md"
    assert decision("Write", other_case) == "allow"

    (vault / "Sources").mkdir()
    (vault / "Sources" / "s.md").write_text("x")
    assert decision("Edit", vault / "Sources" / "s.md") == "ask"
    assert decision("Write", vault / "Sources" / "new.md") == "allow"


def test_approve_never_waves_through_files_that_are_code_or_instructions(run, vault):
    """An unattended run that read an injected line must not change, unasked, what later
    sessions load as instructions or what Templater runs as code (D120)."""

    def decision(path: Path, **env: str):
        _, out = run("approve", stdin=hook_input("Write", path), vault=vault, env=env)
        return out["hookSpecificOutput"]["permissionDecision"] if out else None

    assert decision(vault / ".claude" / "skills" / "x" / "SKILL.md") is None
    assert decision(vault / ".claude" / "agents" / "a.md") is None
    assert decision(vault / ".Claude" / "commands" / "c.md") is None
    assert decision(vault / "CLAUDE.md") == "ask"
    assert decision(vault / "Notes" / "claude.md") == "ask"
    assert decision(vault / "AGENTS.md") == "ask"
    assert decision(vault / "About.md") == "ask"
    assert decision(vault / "Templates" / "Generated" / "Task.md") == "ask"
    assert decision(vault / "Templates" / "Daily.md") == "ask"
    assert decision(vault / ".synapsidian" / "extensions" / "x" / "templates" / "task.md") == "ask"
    off = {"CLAUDE_PLUGIN_OPTION_AUTO_APPROVE_VAULT_EDITS": "false"}
    assert decision(vault / "Templates" / "Generated" / "Task.md", **off) == "ask"
    assert decision(vault / "Notes" / "Templates.md") == "allow"  # only the top-level folder


def test_approve_and_writers_refuse_a_vault_that_is_too_broad(run, vault, tmp_path):
    home = Path.home()
    _, out = run(
        "approve", stdin=hook_input("Write", home / ".claude" / "CLAUDE.md"), env={"SYNAPSIDIAN_VAULT": str(home)}
    )
    assert out is None
    rc, out = run("note", "--vault", "/", "new", "--type", "idea", "--title", "X", env={"SYNAPSIDIAN_VAULT": "/"})
    assert rc == 2 and not out["ok"]


def test_writers_refuse_a_vault_argument_that_is_not_a_vault(run, vault, tmp_path):
    """`synapsidian *` is pre-approved, so `--vault` must not make it write anywhere."""
    (vault / "About.md").write_text("---\ntype: about\n---\n")
    elsewhere = tmp_path / "repo"
    elsewhere.mkdir()
    idea = ["new", "--type", "idea", "--field", "summary=s"]
    rc, out = run("note", "--vault", str(elsewhere), *idea, "--title", "Planted", vault=vault)
    assert rc == 2 and not list(elsewhere.rglob("*.md"))
    rc, out = run("note", "--vault", str(vault), *idea, "--title", "Fine", vault=vault)
    assert rc == 0 and out["ok"]


def test_approve_matches_protected_paths_in_either_unicode_form(run, vault):
    import unicodedata

    (vault / "About.md").write_text("---\ntype: about\nprotected:\n  - Prywatne/Żółw\n---\n")
    for form in ("NFC", "NFD"):
        path = vault / unicodedata.normalize(form, "Prywatne/Żółw/x.md")
        _, out = run("approve", stdin=hook_input("Edit", path), vault=vault)
        assert out["hookSpecificOutput"]["permissionDecision"] == "ask", form


def test_approve_asks_before_writing_under_a_protected_path(run, vault, tmp_path):
    def decision(path: Path, **env: str):
        _, out = run("approve", stdin=hook_input("Edit", path), vault=vault, env=env)
        return out["hookSpecificOutput"]["permissionDecision"] if out else None

    (vault / "About.md").write_text(RULES_ABOUT)
    off = {"CLAUDE_PLUGIN_OPTION_AUTO_APPROVE_VAULT_EDITS": "false"}
    assert decision(vault / "Personal" / "Diary" / "x.md") == "ask"
    assert decision(vault / "personal" / "x.md") == "ask"  # case-insensitive, as the file system is
    assert decision(vault / "Personal" / "x.md", **off) == "ask"  # protection doesn't depend on auto-approve
    assert decision(vault / "Journal" / "Private.md") == "ask"
    assert decision(vault / "Journal" / "Public.md") == "allow"
    assert decision(vault / "Personality.md") == "allow"  # a prefix of a name is not the folder
    assert decision(tmp_path / "Personal" / "x.md") is None


def test_brief_labels_each_about_section_and_subsection(run, fixture_vault):
    (fixture_vault / "About.md").write_text(
        "---\ntype: about\nrole: Engineer\ninterests: [chess, hiking]\nlanguage: Polish\n---\n"
        "## Who I am\nI build things.\n\n## Current focus\nShip v2.\n\n### Work\nLaunch X.\n\n"
        "## How I work\n\n\n## Rules\n- Be brief.\n"
    )
    _, out = run("brief", "--plain", "--today", "2026-10-16", vault=fixture_vault)
    assert "- interests: chess, hiking" in out and "- language: Polish" in out
    assert "- Who I am: I build things." in out
    assert "- Current focus: Ship v2." in out and "- Current focus / Work: Launch X." in out
    assert "How I work" not in out.split("### Vault rules")[0]  # an empty section says nothing
    _, minimal = run("brief", "--plain", "--minimal", vault=fixture_vault)
    assert "I build things." not in minimal and "- role: Engineer" in minimal


def test_the_brief_still_answers_when_the_schema_wont_load(run, vault):
    # An extension installed by a newer core (D161): the session and the dock keep their brief.
    folder = vault / ".synapsidian" / "extensions" / "newer"
    folder.mkdir(parents=True)
    (folder / "schema.yaml").write_text("extend:\n  about:\n    lanes: [a]\n")
    (vault / "About.md").write_text("---\ntype: about\nrole: Engineer\n---\n")
    code, out = run("brief", "--plain", vault=vault)
    assert code == 0 and "role: Engineer" in out
    assert "The vault's schema did not load, so synapsidian can't write notes: extension newer" in out
    code, out = run("brief", "--json", vault=vault)
    assert code == 0 and out["ok"] is True
