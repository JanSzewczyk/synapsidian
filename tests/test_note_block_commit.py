from __future__ import annotations

import datetime as dt
import json
import subprocess
import threading
from pathlib import Path

from block import replace_block
from synapsidianlib import frontmatter, gitops, links
from synapsidianlib import vault as vault_notes


def log(vault: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(vault), "log", "--format=%s|%an"], capture_output=True, text=True)
    return out.stdout.splitlines()


def test_task_ids_increase_and_count_archived_tasks(run, vault):
    code, first = run("note", "new", "--type", "task", "--title", "One", "--field", "summary=s", vault=vault)
    assert code == 0 and first["id"] == "T1"
    (vault / "Archive" / "Tasks").mkdir(parents=True)
    (vault / "Tasks" / "T1 One.md").rename(vault / "Archive" / "Tasks" / "T1 One.md")
    _, second = run("note", "new", "--type", "task", "--title", "Two", "--field", "summary=s", vault=vault)
    assert second["id"] == "T2"
    assert second["rel"] == "Tasks/T2 Two.md"


def test_new_refuses_to_overwrite_and_validates_input(run, projects_vault):
    vault = projects_vault
    args = ("new", "--type", "project", "--title", "Alpha", "--field", "summary=s")
    assert run("note", *args, vault=vault)[0] == 0
    code, result = run("note", *args, vault=vault)
    assert code == 3 and result["rel"] == "Projects/Alpha/Alpha.md"  # a hub lives in a folder of its own
    assert run("note", "new", "--type", "project", "--title", "B", vault=vault)[0] == 2  # no summary
    # Enum and pattern values are checked on write, not only by the Edit hook afterwards.
    code, bad = run("note", "new", "--type", "project", "--title", "D", "--field", "summary=s",
                    "--field", "status=someday", vault=vault)  # fmt: skip
    assert code == 2 and "allowed" in bad["error"] and not (vault / "Projects/D/D.md").exists()
    hub = "Projects/Alpha/Alpha.md"
    code, bad = run("note", "set", "--file", hub, "--field", "status=someday", vault=vault)
    assert code == 2 and "status: active" in (vault / hub).read_text()
    assert (
        run(
            "note",
            "new",
            "--type",
            "task",
            "--title",
            "C",
            "--field",
            "summary=s",
            "--field",
            "due=friday",
            vault=vault,
        )[0]
        == 2
    )
    assert (
        run(
            "note",
            "new",
            "--type",
            "task",
            "--title",
            "C",
            "--field",
            "summary=s",
            "--field",
            "colour=red",
            vault=vault,
        )[0]
        == 2
    )


def test_new_writes_typed_frontmatter_and_template(run, work_vault):
    vault = work_vault
    _, result = run(
        "note",
        "new",
        "--type",
        "meeting",
        "--title",
        "Mikael",
        "--field",
        "kind=1-1",
        "--field",
        "date=2026-10-14",
        "--field",
        "attendees=Mikael Berg,Anna Nowak",
        "--field",
        "summary=Weekly sync",
        vault=vault,
    )
    assert result["rel"] == "Meetings/2026-10-14 1-1 Mikael.md"
    parsed = frontmatter.parse((vault / result["rel"]).read_text())
    assert parsed.meta["attendees"] == ["[[Mikael Berg]]", "[[Anna Nowak]]"]
    assert parsed.meta["date"] == dt.date(2026, 10, 14)
    assert "## Action items" in parsed.body


def test_goals_note_kinds_and_follow_ups_as_the_brief_and_review_read_them(run, vault):
    def new(type_name: str, title: str, *fields: str) -> tuple[str, frontmatter.Parsed]:
        args = [a for f in ("summary=s", *fields) for a in ("--field", f)]
        code, out = run("note", "new", "--type", type_name, "--title", title, *args, vault=vault)
        assert code == 0, out
        return out["rel"], frontmatter.parse((vault / out["rel"]).read_text())

    def titles(*where: str) -> list[str]:
        _, out = run("query", "notes", *(a for w in where for a in ("--where", w)), vault=vault)
        return sorted(n["title"] for n in out["notes"])

    rel, goal = new("goal", "Run a marathon", "target=2026-11-20", "progress=40", "horizon=year")
    assert rel == "Goals/Run a marathon.md" and goal.meta["status"] == "active"
    assert "## Progress log" in goal.body
    new("goal", "Learn Rust", "target=2027-06-01")
    assert titles("type=goal", "status=active", "target<=2026-11-27") == ["Run a marathon"]

    assert "## Key claims" in new("note", "Thinking, Fast and Slow", "kind=literature")[1].body
    assert "## How it works" in new("note", "Loss aversion", "kind=concept")[1].body
    assert "## Overview" in new("note", "Plain", "area=domain")[1].body
    assert run("note", "new", "--type", "note", "--title", "X", "--field", "summary=s", "--field", "kind=essay",
               vault=vault)[0] == 2  # fmt: skip

    rel, alex = new("person", "Alex", "last_contact=2026-10-01", "follow_up=2026-10-28")
    assert "## How we help each other" in alex.body and "## Open topics" in alex.body
    new("person", "Sam", "follow_up=2026-11-15")
    assert titles("type=person", "follow_up<=2026-10-28") == ["Alex"]
    run("note", "set", "--file", rel, "--field", "follow_up=", vault=vault)
    assert titles("type=person", "follow_up<=2026-10-28") == []


def test_body_from_stdin_is_kept_verbatim(run, vault):
    _, result = run(
        "note",
        "new",
        "--type",
        "capture",
        "--title",
        "Idea",
        "--body-file",
        "-",
        stdin="Zażółć gęślą jaźń\nhttps://example.com\n",
        vault=vault,
    )
    assert frontmatter.parse((vault / result["rel"]).read_text()).body == "Zażółć gęślą jaźń\nhttps://example.com\n"


def test_daily_is_idempotent_and_set_closes_tasks(run, vault):
    assert run("note", "daily", "--date", "2026-10-13", vault=vault)[1]["created"] is True
    assert run("note", "daily", "--date", "2026-10-13", vault=vault)[1]["created"] is False
    _, task = run("note", "new", "--type", "task", "--title", "T", "--field", "summary=s", vault=vault)
    _, changed = run("note", "set", "--file", task["rel"], "--field", "status=done", vault=vault)
    assert changed["changed"]["status"] == "done" and "done_on" in changed["changed"]
    assert run("note", "set", "--file", "../outside.md", "--field", "status=done", vault=vault)[0] == 2


def test_folder_by_files_new_notes_and_set_moves_them(run, projects_vault):
    vault = projects_vault
    new = ("note", "new", "--type", "task", "--field", "summary=s")
    _, alpha = run(*new, "--title", "Ship", "--field", "project=Alpha", vault=vault)
    _, loose = run(*new, "--title", "Loose", vault=vault)
    assert alpha["rel"] == "Projects/Alpha/Tasks/T1 Ship.md" and loose["rel"] == "Tasks/T2 Loose.md"

    _, moved = run("note", "set", "--file", alpha["rel"], "--field", "project=Beta", vault=vault)
    assert moved["from"] == alpha["rel"] and moved["rel"] == "Projects/Beta/Tasks/T1 Ship.md"
    assert not (vault / alpha["rel"]).exists()
    assert frontmatter.parse((vault / moved["rel"]).read_text()).meta["project"] == "[[Beta]]"

    _, stays = run("note", "set", "--file", moved["rel"], "--field", "status=doing", vault=vault)
    assert "from" not in stays and stays["rel"] == moved["rel"]  # other fields never move a note

    # Both paths go to the commit, so git records a move, not a copy.
    run("commit", "--skill", "task", "--message", "seed", loose["rel"], moved["rel"], vault=vault)
    _, back = run("note", "set", "--file", moved["rel"], "--field", "project=", vault=vault)
    assert back["rel"] == "Tasks/T1 Ship.md"
    run("commit", "--skill", "task", "--message", "unfile", back["from"], back["rel"], vault=vault)
    status = subprocess.run(
        ["git", "-C", str(vault), "status", "--porcelain", "--", "Tasks", "Projects"], capture_output=True, text=True
    )
    assert status.stdout.strip() == ""  # nothing left behind at the old path

    # An occupied target refuses before anything is written; an archived note stays archived.
    (vault / "Projects/Gamma/Tasks").mkdir(parents=True)
    (vault / "Projects/Gamma/Tasks/T1 Ship.md").write_text("---\ntype: capture\n---\n")
    code, _ = run("note", "set", "--file", back["rel"], "--field", "project=Gamma", vault=vault)
    assert code == 3 and "[[Gamma]]" not in (vault / back["rel"]).read_text()
    _, archived = run("note", "archive", "--file", loose["rel"], vault=vault)
    _, kept = run("note", "set", "--file", archived["to"], "--field", "project=Alpha", vault=vault)
    assert kept["rel"] == archived["to"] and "from" not in kept


def test_new_refuses_a_file_name_another_note_already_has(run, vault):
    assert run("note", "new", "--type", "note", "--title", "Alex", "--field", "summary=s", vault=vault)[0] == 0
    code, out = run("note", "new", "--type", "person", "--title", "alex", "--field", "summary=s", vault=vault)
    assert code == 3 and out["rel"] == "Notes/Alex.md"  # [[Alex]] could no longer tell them apart
    assert not (vault / "People/alex.md").exists()


def test_closing_a_recurring_task_files_the_next_one(run, vault):
    """D124: `repeat` on a task; closing it files the next with the due date moved on."""
    from note import add_interval

    assert add_interval(dt.date(2026, 1, 31), "1m") == dt.date(2026, 2, 28)
    assert add_interval(dt.date(2028, 2, 29), "1y") == dt.date(2029, 2, 28)
    assert add_interval(dt.date(2026, 12, 15), "2w") == dt.date(2026, 12, 29)
    assert add_interval(dt.date(2026, 11, 30), "3m") == dt.date(2027, 2, 28)

    future = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    fields = ("--field", "summary=Rent", "--field", f"due={future}", "--field", "repeat=1m", "--field", "priority=high",
              "--field", "blocked_by=[[Sign the lease]]")  # fmt: skip
    _, task = run("note", "new", "--type", "task", "--title", "Pay rent", *fields, vault=vault)
    assert run("note", "new", "--type", "task", "--title", "Bad", "--field", "summary=s", "--field", "repeat=monthly",
               vault=vault)[0] == 2  # fmt: skip
    code, closed = run("note", "set", "--file", task["rel"], "--field", "status=done", vault=vault)
    assert code == 0
    nxt = closed["next"]
    assert nxt["id"] == "T2" and nxt["rel"] == "Tasks/T2 Pay rent.md"
    assert nxt["due"] == add_interval(dt.date.fromisoformat(future), "1m").isoformat()
    text = (vault / nxt["rel"]).read_text()
    meta = frontmatter.parse(text).meta
    assert meta["status"] == "todo" and meta["repeat"] == "1m" and meta["priority"] == "high" and "done_on" not in meta
    assert "blocked_by" not in meta  # what this occurrence waited on, not the next one (D144)
    assert f"repeats [[{Path(task['rel']).stem}]]" in text
    _, again = run("note", "set", "--file", task["rel"], "--field", "status=done", vault=vault)
    assert "next" not in again  # closing a closed task twice files nothing more

    overdue = (dt.date.today() - dt.timedelta(days=20)).isoformat()
    _, late = run("note", "new", "--type", "task", "--title", "Water plants", "--field", "summary=s",
                  "--field", f"due={overdue}", "--field", "repeat=1w", vault=vault)  # fmt: skip
    _, done = run("note", "set", "--file", late["rel"], "--field", "status=done", vault=vault)
    assert dt.date.fromisoformat(done["next"]["due"]) > dt.date.today()  # stepped past today, on the same weekday
    assert (dt.date.fromisoformat(done["next"]["due"]) - dt.date.fromisoformat(overdue)).days % 7 == 0


def test_person_and_goal_notes_embed_their_linked_work_and_older_ones_can_get_it(run, vault):
    """D133: object pages - a person's meetings and tasks, a goal's tasks, as embedded Bases."""
    _, person = run("note", "new", "--type", "person", "--title", "Alex", "--field", "summary=s", vault=vault)
    text = (vault / person["rel"]).read_text()
    assert "## Meetings and tasks\n\n```base\n" in text and "note.attendees.contains(this)" in text
    _, goal = run("note", "new", "--type", "goal", "--title", "Run a marathon", "--field", "summary=s", vault=vault)
    assert "note.goal == this" in (vault / goal["rel"]).read_text()
    _, task = run("note", "new", "--type", "task", "--title", "Buy shoes", "--field", "summary=s",
                  "--field", "goal=Run a marathon", vault=vault)  # fmt: skip
    assert frontmatter.parse((vault / task["rel"]).read_text()).meta["goal"] == "[[Run a marathon]]"

    old = vault / "People" / "Sam.md"
    old.write_text("---\ntype: person\ncreated: 2026-10-01\nsummary: s\n---\n## Context\n\nMine.\n")
    code, section = run("note", "section", "--type", "person", "--section", "Meetings and tasks", vault=vault)
    assert code == 0 and section.startswith("```base")
    _, filled = run("note", "fill", "--file", "People/Sam.md", "--section", "Meetings and tasks",
                    stdin=section + "\n", vault=vault)  # fmt: skip
    assert filled["status"] == "added" and "Mine." in old.read_text() and "```base" in old.read_text()
    assert run("note", "section", "--type", "person", "--section", "Nope", vault=vault)[0] == 2


def test_archive_moves_without_overwriting(run, vault):
    _, cap = run("note", "new", "--type", "capture", "--title", "x", vault=vault)
    _, moved = run("note", "archive", "--file", cap["rel"], vault=vault)
    assert moved["to"] == f"Archive/{cap['rel']}" and (vault / moved["to"]).exists()
    assert not (vault / cap["rel"]).exists()


def test_block_set_adds_a_missing_section_only_when_asked(run, vault):
    run("note", "daily", "--date", "2026-10-14", vault=vault)
    rel = "Daily/2026-10-14.md"
    assert run("block", "set", "--file", rel, "--name", "standup", stdin="- x\n", vault=vault)[0] == 3
    code, _ = run(
        "block", "set", "--file", rel, "--name", "standup", "--section", "Stand-up", stdin="- x\n", vault=vault
    )
    assert code == 0
    text = (vault / rel).read_text()
    assert text.endswith("## Stand-up\n<!-- @generated:standup -->\n- x\n<!-- @end -->\n")
    run("block", "set", "--file", rel, "--name", "standup", "--section", "Stand-up", stdin="- y\n", vault=vault)
    assert (vault / rel).read_text().count("## Stand-up") == 1


def test_block_set_puts_a_missing_block_inside_its_section_or_before_another():
    from block import add_section

    text = "## Goal\nShip.\n\n## Facts\nMine.\n\n## Log\n- old\n"
    out = add_section(text, "Facts", "facts", "- a\n", hashed=True)
    assert out.count("## Facts") == 1  # an existing section gets the block, never a second heading
    assert "## Facts\nMine.\n<!-- @generated:facts sha=" in out and out.endswith("<!-- @end -->\n\n## Log\n- old\n")

    repo = "## Repo\n<!-- @generated:repo -->\n- b\n<!-- @end -->\n"
    assert add_section(text, "Repo", "repo", "- b\n", before="Log") == text.replace("## Log", f"{repo}\n## Log")
    assert add_section(text, "Repo", "repo", "- b\n", before="Missing").endswith(f"- old\n\n{repo}")


def test_replace_block_only_touches_the_named_block():
    text = "a\n<!-- @generated:brief -->\nold\n<!-- @end -->\nmine\n<!-- @generated:devlog -->\nkeep\n<!-- @end -->\n"
    out = replace_block(text, "brief", "- new\n")
    assert out == text.replace("old\n", "- new\n")
    assert replace_block(out, "brief", "") == text.replace("old\n", "")


def test_a_block_that_lost_its_end_line_is_refused_not_guessed(run, vault):
    """D121: the lazy match used to run to the next block's @end and replace the user's notes."""
    run("note", "daily", "--date", "2026-10-30", vault=vault)
    rel = "Daily/2026-10-30.md"
    path = vault / rel
    text = (
        "---\ntype: daily\ndate: 2026-10-30\ncreated: 2026-10-30\n---\n## Agenda\n<!-- @generated:agenda -->\n"
        "- 10:00 old\n\n## Notes\nMy important handwritten notes\n\n## Devlog\n<!-- @generated:devlog -->\n"
        "- did x\n<!-- @end -->\n"
    )
    path.write_text(text)
    code, out = run("block", "set", "--file", rel, "--name", "agenda", stdin="- 11:00 new\n", vault=vault)
    assert code == 5 and "lost its" in out["error"]
    assert path.read_text() == text
    assert run("block", "get", "--file", rel, "--name", "agenda", vault=vault)[0] == 5
    code, out = run("block", "set", "--file", rel, "--name", "devlog", stdin="- did y\n", vault=vault)
    assert code == 0 and "My important handwritten notes" in path.read_text() and "- did y" in path.read_text()
    _, checked = run("block", "check", "--file", rel, vault=vault)
    assert {"name": "agenda", "status": "broken"} in checked["blocks"]


def test_set_keeps_values_synapsidian_did_not_touch(run, vault):
    """D121: YAML 1.1 re-typing turned `10:30` into 630 and `yes` into true on every `note set`."""
    (vault / "Ideas").mkdir()
    path = vault / "Ideas" / "Room.md"
    path.write_text(
        "---\ntype: idea\ncreated: 2026-10-01\nsummary: s\nstatus: new\ntime: 10:30\nanswer: yes\n---\nBody\n"
    )
    code, _ = run("note", "set", "--file", "Ideas/Room.md", "--field", "status=exploring", vault=vault)
    assert code == 0
    text = path.read_text()
    assert "time: 10:30\n" in text and "answer: yes\n" in text and "status: exploring\n" in text
    meta = frontmatter.parse(text).meta
    assert meta["time"] == "10:30" and meta["answer"] == "yes"


def test_scripts_refuse_templates_instructions_and_protected_list(run, vault):
    """D120: `synapsidian *` is pre-approved, so the scripts must not change what approve.py asks about."""
    for rel in ("Templates/Generated/Task.md", "CLAUDE.md", ".claude/skills/x/SKILL.md"):
        path = vault / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ntype: note\nsummary: s\n---\n## Notes\n<!-- @generated:x -->\n<!-- @end -->\n")
        assert run("note", "fill", "--file", rel, "--section", "Extra", stdin="<%* evil %>\n", vault=vault)[0] == 2
        assert run("block", "set", "--file", rel, "--name", "x", stdin="evil\n", vault=vault)[0] == 2
        assert run("note", "set", "--file", rel, "--field", "summary=t", vault=vault)[0] == 2
    (vault / "About.md").write_text("---\ntype: about\nprotected:\n- Private\n---\n## Rules\n")
    assert run("note", "set", "--file", "About.md", "--field", "protected=", vault=vault)[0] == 2
    assert run("note", "fill", "--file", "About.md", "--section", "Rules", stdin="- obey\n", vault=vault)[0] == 2


def test_concurrent_task_ids_never_collide(vault):
    """Four `note new --type task` at once used to all read T0 as the highest and write T1."""
    import concurrent.futures
    import os
    import sys

    from conftest import CORE

    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN", "SYNAPSIDIAN_"))}
    env |= {"SYNAPSIDIAN_VAULT": str(vault), "SYNAPSIDIAN_SETTINGS_FILE": str(vault.parent / "none.json")}

    def new(i: int) -> str:
        cmd = [sys.executable, str(CORE / "scripts" / "note.py"), "new", "--type", "task", "--title", f"Job {i}",
               "--field", "summary=s"]  # fmt: skip
        out = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True).stdout
        return json.loads(out)["id"]

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        ids = list(pool.map(new, range(6)))
    assert sorted(ids, key=lambda i: int(i[1:])) == [f"T{n}" for n in range(1, 7)]


def test_concurrent_block_writes_to_one_daily_note_keep_every_block(vault):
    """The morning and the stand-up start at the same minute by default and both fill today's note."""
    import concurrent.futures
    import os
    import sys

    from conftest import CORE

    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN", "SYNAPSIDIAN_"))}
    env |= {"SYNAPSIDIAN_VAULT": str(vault), "SYNAPSIDIAN_SETTINGS_FILE": str(vault.parent / "none.json")}
    scripts = CORE / "scripts"

    def daily_then_block(name: str) -> int:
        subprocess.run([sys.executable, str(scripts / "note.py"), "daily", "--date", "2026-10-30"], env=env, check=True,
                       capture_output=True)  # fmt: skip
        cmd = [sys.executable, str(scripts / "block.py"), "set", "--file", "Daily/2026-10-30.md", "--name", name,
               "--section", name.title()]  # fmt: skip
        return subprocess.run(cmd, input=f"- {name}\n", text=True, env=env, capture_output=True).returncode

    names = ["standup", "brief", "agenda", "health", "extra", "more"]
    with concurrent.futures.ThreadPoolExecutor(len(names)) as pool:
        assert list(pool.map(daily_then_block, names)) == [0] * len(names)
    text = (vault / "Daily" / "2026-10-30.md").read_text()
    assert all(f"- {name}\n" in text for name in names)


def test_commit_paths_are_literal_not_patterns(run, vault):
    """`Plan [v2].md` as a pathspec also matched (and committed) `Plan 2.md` and `Plan v.md`."""
    notes = vault / "Notes"
    notes.mkdir()
    for name in ("Plan [v2].md", "Plan 2.md", "Plan v.md"):
        (notes / name).write_text("x")
    code, result = run("commit", "--skill", "save", "--message", "m", "Notes/Plan [v2].md", vault=vault)
    assert code == 0 and result["committed"]
    tracked = subprocess.run(["git", "-C", str(vault), "ls-files"], capture_output=True, text=True).stdout.split("\n")
    assert [t for t in tracked if t] == ["Notes/Plan [v2].md"]


def test_fill_writes_only_empty_or_missing_sections(run, work_vault):
    vault = work_vault
    _, made = run("note", "new", "--type", "meeting", "--title", "Alex", "--field", "date=2026-10-19",
                  "--field", "kind=1-1", "--field", "summary=s", vault=vault)  # fmt: skip
    rel = made["rel"]
    path = vault / rel
    path.write_text(path.read_text().replace("## Talking points\n", "## Talking points\n\n### Mine\n\nKeep me.\n"))
    before = path.read_text()
    fill = ("note", "fill", "--file", rel)

    code, out = run(*fill, "--section", "Notes", stdin="Summary [00:02:45]\n", vault=vault)
    assert code == 0 and out["status"] == "filled"
    _, out = run(*fill, "--section", "Talking points", stdin="overwrite\n", vault=vault)
    assert out["status"] == "kept"
    _, out = run(*fill, "--section", "decisions", "--before", "Action items", stdin="- Agreed\n", vault=vault)
    assert out["status"] == "added"
    _, out = run(*fill, "--section", "Decisions", stdin="- Again\n", vault=vault)  # re-run: now filled, kept
    assert out["status"] == "kept"

    text = path.read_text()
    assert text.startswith(before.split("## Notes")[0])  # frontmatter and the user's section byte for byte
    assert "overwrite" not in text and "Again" not in text
    assert "## Notes\nSummary [00:02:45]\n\n## decisions\n- Agreed\n\n## Action items" in text

    code, bad = run(*fill, "--section", "Action items", stdin="token ghp_" + "a" * 30 + "\n", vault=vault)
    assert code == 2 and bad["problems"] and "ghp_" not in path.read_text()


def test_fill_ignores_headings_inside_code_fences():
    from note import fill_section

    text = "## Notes\n```\n## Action items\n```\n\n## Action items\n"
    out, status = fill_section(text, "Action items", "- [ ] x")
    assert status == "filled" and out == text + "- [ ] x\n"
    assert fill_section(text, "Notes", "y") == (text, "kept")


def test_a_shorter_fence_inside_a_longer_one_is_content():
    from synapsidianlib.sections import sections

    lines = ["## Notes\n", "````md\n", "```\n", "## Fake\n", "```\n", "````\n", "## Real\n"]
    assert [title for title, _, _ in sections(lines)] == ["Notes", "Real"]


def test_commit_only_listed_files_with_skill_prefix(run, vault):
    (vault / "a.md").write_text("a")
    (vault / "b.md").write_text("b")
    code, result = run("commit", "--skill", "save", "--message", "first   one", "a.md", vault=vault)
    assert code == 0 and result["committed"]
    assert log(vault) == ["synapsidian(save): first one|Test User"]
    status = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout.strip() == "?? b.md"
    assert run("commit", "--skill", "save", "--message", "again", "a.md", vault=vault)[1]["committed"] is False


def test_commit_records_session_and_locks_in_the_vaults_git_dir(run, vault, tmp_path):
    """State shared by every process writing this vault, whatever data dir each one was given."""
    (vault / "a.md").write_text("a")
    run("commit", "--skill", "save", "--message", "m", "--record-session", "abc-123", "a.md", vault=vault)
    assert '"session_id": "abc-123"' in (vault / ".git" / "synapsidian" / "saved-sessions.jsonl").read_text()
    assert (vault / ".git" / "synapsidian" / "vault.lock").exists()
    assert not (tmp_path / "data" / "saved-sessions.jsonl").exists()


def test_unsubstituted_placeholder_and_wrong_case_still_resolve_the_vault(run, vault, tmp_path):
    """Live-session findings: `${user_config.vault_path}` left literal, and `Synapsidian` vs `synapsidian` on disk."""
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"pluginConfigs": {"synapsidian@synapsidian": {"options": {"vault_path": str(vault)}}}})
    )
    code, result = run(
        "note",
        "--vault",
        "${user_config.vault_path}",
        "new",
        "--type",
        "capture",
        "--title",
        "x",
        env={"SYNAPSIDIAN_SETTINGS_FILE": str(settings)},
    )
    assert code == 0 and result["rel"] == "Inbox/" + Path(result["rel"]).name

    upper = str(vault).replace("/Synapsidian", "/SYNAPSIDIAN")
    code, result = run("note", "--vault", upper, "set", "--file", result["rel"], "--field", "source_url=u")
    assert code == 0 and result["rel"].startswith("Inbox/")


def test_commit_includes_archive_moves(run, vault):
    (vault / "Inbox").mkdir()
    (vault / "Inbox" / "x.md").write_text("x")
    run("commit", "--skill", "capture", "--message", "x", "Inbox/x.md", vault=vault)
    run("note", "archive", "--file", "Inbox/x.md", vault=vault)
    _, result = run("commit", "--skill", "save", "--message", "file", "Inbox/x.md", "Archive/Inbox/x.md", vault=vault)
    assert result["committed"]
    tracked = subprocess.run(["git", "-C", str(vault), "ls-files"], capture_output=True, text=True).stdout
    assert tracked.strip() == "Archive/Inbox/x.md"


def test_commit_adds_the_old_path_of_an_archived_note(run, vault):
    """2026-10-13: a review run listed only `Archive/Welcome.md`, leaving the deletion uncommitted."""
    (vault / "Welcome.md").write_text("w")
    run("commit", "--skill", "setup", "--message", "track", "Welcome.md", vault=vault)
    run("note", "archive", "--file", "Welcome.md", vault=vault)
    _, result = run("commit", "--skill", "review", "--message", "archive", "Archive/Welcome.md", vault=vault)
    assert result["committed"] and result["added_archive_sources"] == ["Welcome.md"]
    status = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout.strip() == ""


def test_commit_reports_files_another_commit_swept_up(run, vault):
    """Obsidian Git's timer committing a run's file before the run does: say so, don't stay silent."""
    (vault / "a.md").write_text("a")
    (vault / "b.md").write_text("b")
    run("commit", "--skill", "save", "--message", "start", "a.md", "b.md", vault=vault)
    (vault / "a.md").write_text("a2")
    (vault / "b.md").write_text("b2")
    subprocess.run(["git", "-C", str(vault), "commit", "-qam", "vault backup: 2026-10-14 07:22:50"], check=True)
    (vault / "c.md").write_text("c")
    _, result = run("commit", "--skill", "evening", "--message", "devlog", "a.md", "c.md", vault=vault)
    assert result["committed"] and [s["path"] for s in result["swept"]] == ["a.md"]
    assert result["swept"][0]["message"] == "vault backup: 2026-10-14 07:22:50" and "warning" in result

    _, again = run("commit", "--skill", "save", "--message", "nothing new", "c.md", vault=vault)
    assert again["committed"] is False and "swept" not in again  # its own earlier commit is not a sweep


def test_commit_reports_the_broken_links_it_added_and_commits_anyway(run, vault):
    """D158: a dated note linked without its date is reported to the run that wrote the link;
    a link that was already broken, one in code and one in a verbatim copy are not."""
    for folder in ("Decisions", "Sources"):
        (vault / folder).mkdir()
    (vault / "Decisions" / "2026-10-13 Use CSV.md").write_text("d")
    (vault / "Sources" / "copy.md").write_text("[[Nowhere]]")
    (vault / "Log.md").write_text("- [[Gone long ago]]\n")
    run("commit", "--skill", "save", "--message", "start", "Log.md", vault=vault)

    files = ("Log.md", "Sources/copy.md", "Decisions/2026-10-13 Use CSV.md")
    (vault / "Log.md").write_text("- [[Gone long ago]]\n- [[Use CSV]], [[2026-10-13 use csv|decided]], `[[code]]`\n")
    _, result = run("commit", "--skill", "evening", "--message", "devlog", *files, vault=vault)
    assert result["committed"] and result["broken_links"] == [{"rel": "Log.md", "link": "Use CSV"}]

    (vault / "Log.md").write_text("- [[Gone long ago]]\n- [[2026-10-13 Use CSV]]\n")
    _, fixed = run("commit", "--skill", "evening", "--message", "fix link", *files, vault=vault)
    assert fixed["committed"] and "broken_links" not in fixed

    # Files a script owns are not the run's to fix; a moved note's old links are not new.
    for owned in ("Templates/Generated/T.md", "Maps/Plan.excalidraw.md"):
        (vault / owned).parent.mkdir(parents=True, exist_ok=True)
        (vault / owned).write_text("[[Nowhere]]")
    (vault / "Notes").mkdir()
    (vault / "Log.md").rename(vault / "Notes" / "Log.md")
    moved = ("Log.md", "Notes/Log.md", "Templates/Generated/T.md", "Maps/Plan.excalidraw.md")
    _, result = run("commit", "--skill", "setup", "--message", "move", *moved, vault=vault)
    assert result["committed"] and "broken_links" not in result
    # The health check walks `vault.iter_notes`; the commit check must leave out what that does.
    assert {d for d in vault_notes.SKIP_DIRS if not d.startswith(".")} == links.NOT_NOTE_DIRS
    assert vault_notes.NOT_NOTE_SUFFIXES == links.NOT_NOTE_SUFFIXES


def test_block_set_and_note_set_refuse_a_credential(run, vault):
    """D158: every script that writes text into the vault screens it, not only `note new` and `fill`."""
    token = "sk-ant-" + "x" * 30
    daily = run("note", "daily", "--date", "2026-10-13", vault=vault)[1]["rel"]
    code, bad = run("block", "set", "--file", daily, "--name", "devlog", stdin=f"- used {token}\n", vault=vault)
    assert code == 2 and bad["problems"] and token not in (vault / daily).read_text()
    assert run("block", "set", "--file", daily, "--name", "devlog", stdin="- fixed it\n", vault=vault)[0] == 0

    task = run("note", "new", "--type", "task", "--title", "One", "--field", "summary=s", vault=vault)[1]["rel"]
    code, bad = run("note", "set", "--file", task, "--field", f"summary=key {token}", vault=vault)
    assert code == 2 and bad["problems"] and token not in (vault / task).read_text()
    # A note that already holds one (typed in Obsidian) can still be changed: only new values are screened.
    (vault / task).write_text((vault / task).read_text() + f"\n{token}\n")
    assert run("note", "set", "--file", task, "--field", "status=doing", vault=vault)[0] == 0


def test_a_dated_file_name_takes_its_day_from_date_then_created(run, work_vault):
    """D158: a decision written down two days later is filed under the day it was made."""
    vault = work_vault
    decision = ("note", "new", "--type", "decision", "--field", "summary=s")
    code, made = run(*decision, "--title", "Use CSV", "--field", "created=2026-10-11", vault=vault)
    assert code == 0 and made["rel"] == "Decisions/2026-10-11 Use CSV.md"
    code, bad = run(*decision, "--title", "2026-10-11 Use JSON", vault=vault)
    assert code == 2 and "--field created=YYYY-MM-DD" in bad["error"]
    assert [p.name for p in (vault / "Decisions").iterdir()] == ["2026-10-11 Use CSV.md"]
    meeting = ("note", "new", "--type", "meeting", "--title", "Sync", "--field", "summary=s")
    _, made = run(*meeting, "--field", "date=2026-10-12", "--field", "created=2026-10-13", vault=vault)
    assert made["rel"] == "Meetings/2026-10-12 other Sync.md"
    code, bad = run(*meeting, "--title", "2026-10-12 Sync", "--field", "date=2026-10-12", vault=vault)
    assert code == 2 and "--field date=YYYY-MM-DD" in bad["error"]
    # A capture's title is the user's own text: a date at its start is theirs to keep.
    assert run("note", "new", "--type", "capture", "--title", "2026-10-20 dentist", vault=vault)[0] == 0


def test_concurrent_commits_never_sweep_up_each_others_files(vault, tmp_path):
    for i in range(6):
        (vault / f"n{i}.md").write_text(str(i))
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            with gitops.vault_lock(tmp_path, timeout=30):
                assert gitops.commit(vault, [f"n{i}.md"], f"synapsidian(t): note {i}").sha
        except BaseException as exc:  # surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    for i in range(6):
        files = subprocess.run(
            ["git", "-C", str(vault), "log", "--format=", "--name-only", f"--grep=note {i}$"],
            capture_output=True,
            text=True,
        ).stdout.split()
        assert files == [f"n{i}.md"]


def test_note_fill_on_about_takes_only_declared_sections(run, work_vault):
    about = "---\ntype: about\nrole: Engineer\n---\n## Who I am\n\n\n## Current focus\n\n\n## Rules\n- obey\n"
    (work_vault / "About.md").write_text(about)
    fill = lambda *a, text="Text.\n": run("note", "fill", "--file", "About.md", *a, stdin=text, vault=work_vault)  # noqa: E731
    assert fill("--section", "Who I am")[1]["status"] == "filled"
    assert fill("--section", "Who I am", text="Other.\n")[1]["status"] == "kept"
    code, out = fill("--section", "Current focus", "--subsection", "Work", "--before", "Rules")
    assert code == 0 and out["status"] == "added" and out["subsection"] == "Work"
    assert fill("--section", "Current focus", "--subsection", "Work", text="Again.\n")[1]["status"] == "kept"
    text = (work_vault / "About.md").read_text()
    assert "## Current focus\n\n### Work\nText.\n" in text and text.endswith("## Rules\n- obey\n")
    # Never Rules, never a section nobody declared, never a subsection of a section that has none.
    for args in (("--section", "Rules"), ("--section", "Secrets"), ("--section", "Who I am", "--subsection", "X")):
        assert fill(*args)[0] == 2
    assert (work_vault / "About.md").read_text() == text
    assert fill("--section", "Who I am", text="token: ghp_" + "a" * 36 + "\n")[0] == 2
    (work_vault / "Notes").mkdir(exist_ok=True)
    (work_vault / "Notes" / "N.md").write_text("---\ntype: note\nsummary: s\n---\n## Notes\n")
    other = ("--file", "Notes/N.md", "--section", "Notes", "--subsection", "X")
    assert run("note", "fill", *other, stdin="t\n", vault=work_vault)[0] == 2
