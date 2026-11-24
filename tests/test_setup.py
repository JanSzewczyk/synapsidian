from __future__ import annotations

import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

import setup as setup_mod
from conftest import WORK
from synapsidianlib import blocks, schema


def test_apply_creates_layout_commits_once_and_is_idempotent(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    code, first = run(
        "setup",
        "apply",
        "--vault",
        str(vault),
        "--name",
        "Jan Test",
        "--email",
        "jan@example.com",
        "--about",
        "role=Engineer",
        "--about",
        "interests=hiking, chess",
    )
    assert code == 0 and first["commit"]
    about = (vault / "About.md").read_text()
    assert "role: Engineer" in about and "- hiking" in about and "## Who I am" in about
    assert not (vault / "Architecture").exists()  # a work folder comes only with the synapsidian-work extension
    assert {"About.md", "Bases/Tasks.base", ".obsidian/types.json", "Templates/Daily.md"} <= set(first["created"])
    assert {"Templates/Generated/Task.md", "Templates/Generated/Meeting - External.md"} <= set(first["created"])
    assert not (vault / "Templates/Generated/Project.md").exists()  # projects come with synapsidian-projects
    assert all((vault / f).is_dir() for f in setup_mod.FOLDERS)
    log = subprocess.run(["git", "-C", str(vault), "log", "--format=%an <%ae>|%s"], capture_output=True, text=True)
    assert (
        log.stdout.strip() == "Jan Test <jan@example.com>|synapsidian(setup): create vault layout and Obsidian config"
    )

    code, second = run("setup", "apply", "--vault", str(vault))
    assert code == 0
    assert (second["created"], second["updated"], second["commit"]) == ([], [], None)


def test_apply_keeps_settings_the_user_changed(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text(json.dumps({"newFileLocation": "current", "vimMode": True}))
    _, result = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    app = json.loads((vault / ".obsidian" / "app.json").read_text())
    assert app["newFileLocation"] == "current" and app["vimMode"] is True
    assert app["alwaysUpdateLinks"] is True
    assert any("newFileLocation" in k for k in result["kept_user_settings"])


def legacy_core_templates(vault: Path, folder: str = "Templates") -> Path:
    """What synapsidian's setup wrote before D110: core Templates on, its folder `Templates`."""
    obsidian = vault / ".obsidian"
    obsidian.mkdir(parents=True)
    (obsidian / "core-plugins.json").write_text(json.dumps({"templates": True, "graph": True}))
    (obsidian / "templates.json").write_text(json.dumps({"folder": folder, "dateFormat": "YYYY-MM-DD"}))
    return obsidian


def test_apply_turns_off_the_core_templates_synapsidian_left_on_over_its_templater_folder(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    obsidian = legacy_core_templates(vault)
    assert setup_mod.core_templates_clash(vault) == {"folder": "Templates", "own_templates": []}

    _, applied = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    core = json.loads((obsidian / "core-plugins.json").read_text())
    assert core["templates"] is False and core["graph"] is True and core["daily-notes"] is True
    assert applied["core_templates_off"] is True
    assert setup_mod.cmd_check(vault)["core_templates_clash"] is None

    _, again = run("setup", "apply", "--vault", str(vault))
    assert again["core_templates_off"] is False and again["commit"] is None


def test_core_templates_with_the_users_own_templates_stays_on_and_blocks_ready(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    obsidian = legacy_core_templates(vault, folder="Templates/")
    (vault / "Templates").mkdir()
    (vault / "Templates" / "Weekly.md").write_text("# {{date}}\n")
    _, applied = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    assert json.loads((obsidian / "core-plugins.json").read_text())["templates"] is True
    assert applied["core_templates_off"] is False
    assert any("Templates/Weekly.md" in k for k in applied["kept_user_settings"])
    report = setup_mod.cmd_check(vault)
    assert report["core_templates_clash"] == {"folder": "Templates", "own_templates": ["Templates/Weekly.md"]}
    assert not report["ready"]


def test_core_templates_pointed_elsewhere_or_never_configured_is_left_alone(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    obsidian = legacy_core_templates(vault, folder="Templates/Core")
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    assert json.loads((obsidian / "core-plugins.json").read_text())["templates"] is True
    assert setup_mod.core_templates_clash(vault) is None

    fresh = tmp_path / "Fresh"
    run("setup", "apply", "--vault", str(fresh), "--name", "N", "--email", "e@x")
    assert "templates" not in json.loads((fresh / ".obsidian" / "core-plugins.json").read_text())
    assert not (fresh / ".obsidian" / "templates.json").exists()


def test_apply_moves_templates_from_the_folder_before_d119_keeping_an_edited_one(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    # Rewind to a vault an earlier version set up: templates, record and Templater in Templates/Synapsidian/.
    record_path = vault / ".synapsidian/generated-templates.json"
    record = json.loads(record_path.read_text())
    (vault / "Templates/Synapsidian").mkdir()
    for rel in [r for r in record if r.startswith("Templates/Generated/")]:
        old = rel.replace("Templates/Generated/", "Templates/Synapsidian/")
        (vault / rel).rename(vault / old)
        record[old] = record.pop(rel)
    (vault / "Templates/Generated").rmdir()
    record_path.write_text(json.dumps(record))
    (vault / "Templates/Synapsidian/Person.md").write_text("mine now")
    plugin = vault / ".obsidian/plugins/templater-obsidian"
    plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(json.dumps({"id": "templater-obsidian"}))
    hotkeys = ["Mine.md", "Templates/Synapsidian/Task.md", "Templates/Synapsidian/Person.md"]
    (plugin / "data.json").write_text(
        json.dumps({"templates_folder": "Templates/Synapsidian", "enabled_templates_hotkeys": hotkeys})
    )
    subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(vault), "commit", "-qm", "older layout"], check=True)

    _, applied = run("setup", "apply", "--vault", str(vault))
    assert (vault / "Templates/Generated/Task.md").is_file() and not (vault / "Templates/Synapsidian/Task.md").exists()
    assert (vault / "Templates/Synapsidian/Person.md").read_text() == "mine now"  # edited: stays, and is reported
    assert any(k.startswith("Templates/Synapsidian/Person.md") for k in applied["kept_user_settings"])
    templater = json.loads((plugin / "data.json").read_text())
    assert templater["templates_folder"] == "Templates/Generated"
    hotkeys = templater["enabled_templates_hotkeys"]
    assert hotkeys[:2] == ["Mine.md", "Templates/Synapsidian/Person.md"] and "Templates/Generated/Task.md" in hotkeys
    assert "Templates/Synapsidian/Task.md" not in hotkeys
    status = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""

    (vault / "Templates/Synapsidian/Person.md").unlink()
    run("setup", "apply", "--vault", str(vault))
    assert not (vault / "Templates/Synapsidian").exists()


def test_apply_never_overwrites_an_existing_note(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    vault.mkdir()
    (vault / "About.md").write_text("mine")
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    assert (vault / "About.md").read_text() == "mine"


def test_apply_adds_the_rules_section_to_an_older_about_note_once(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    vault.mkdir()
    old = "---\ntype: about\nrole: Engineer\n---\n## Who I am\nMe.\n\n## How I work\n"
    (vault / "About.md").write_text(old)
    _, first = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    text = (vault / "About.md").read_text()
    assert "About.md" in first["updated"]
    assert text.startswith(old) and text.count("## Rules") == 1 and "<!--" in text
    _, second = run("setup", "apply", "--vault", str(vault))
    assert "About.md" not in second["updated"] and (vault / "About.md").read_text() == text


def test_apply_first_commits_what_the_vault_already_held(run, tmp_path):
    """Live finding: an Obsidian-made vault's Welcome.md and settings stayed untracked, so no undo."""
    vault = tmp_path / "Synapsidian"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Welcome.md").write_text("This is your new vault.")
    (vault / ".obsidian" / "app.json").write_text("{}")
    (vault / ".obsidian" / "workspace.json").write_text("{}")

    _, result = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")

    log = subprocess.run(["git", "-C", str(vault), "log", "--format=%s"], capture_output=True, text=True)
    assert log.stdout.splitlines() == [
        "synapsidian(setup): create vault layout and Obsidian config",
        "synapsidian(setup): track existing vault files",
    ]
    first = subprocess.run(
        ["git", "-C", str(vault), "show", "--format=", "--name-only", "HEAD~1"], capture_output=True, text=True
    )
    assert set(first.stdout.split()) == {".gitignore", ".obsidian/app.json", "Welcome.md"}
    original = subprocess.run(["git", "-C", str(vault), "show", "HEAD~1:.obsidian/app.json"], capture_output=True)
    assert original.stdout == b"{}"  # the pre-synapsidian version is recoverable
    status = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""
    assert result["baseline_commit"]


LEGACY_TASK = "---\ntype: task\ncreated: 2026-10-01\nsummary: s\nid: {id}\nstatus: todo\npriority: medium\n---\n"


def git_out(vault: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=True).stdout


def test_apply_renames_legacy_task_ids_and_every_link_in_one_commit(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    (vault / "Tasks").mkdir(parents=True)
    (vault / "Archive" / "Tasks").mkdir(parents=True)
    (vault / "Daily").mkdir()
    (vault / "Tasks" / "ZAD-1 Write the spec.md").write_text(LEGACY_TASK.format(id="ZAD-1"))
    (vault / "Tasks" / "ZAD-10 Ship it.md").write_text(LEGACY_TASK.format(id="'ZAD-10'"))
    (vault / "Archive" / "Tasks" / "ZAD-2 Old one.md").write_text(LEGACY_TASK.format(id="ZAD-2"))
    daily = vault / "Daily" / "2026-10-14.md"
    daily.write_text(
        "---\ntype: daily\ncreated: 2026-10-14\ndate: 2026-10-14\n---\n"
        "- [[ZAD-1 Write the spec]], [[ZAD-10 Ship it|shipping]] and ![[ZAD-2 Old one]]\n"
        "- Notion card ZAD-7 stays as written\n"
    )
    canvas = vault / "Plan.canvas"
    canvas.write_text('{"nodes": [{"type": "file", "file": "Tasks/ZAD-10 Ship it.md"}]}')

    code, result = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")

    assert code == 0
    moved = result["task_ids"]
    renamed = sorted((r["from"], r["to"]) for r in moved["renamed"])
    assert renamed == [("ZAD-1", "T1"), ("ZAD-10", "T10"), ("ZAD-2", "T2")]
    assert (vault / "Tasks" / "T1 Write the spec.md").read_text().count("id: T1\n") == 1
    assert "id: 'T10'" in (vault / "Tasks" / "T10 Ship it.md").read_text()
    assert (vault / "Archive" / "Tasks" / "T2 Old one.md").is_file()
    assert daily.read_text().split("---\n", 2)[2] == (
        "- [[T1 Write the spec]], [[T10 Ship it|shipping]] and ![[T2 Old one]]\n- Notion card ZAD-7 stays as written\n"
    )
    assert "Tasks/T10 Ship it.md" in canvas.read_text()
    assert moved["mentions_left"] == [{"rel": "Daily/2026-10-14.md", "ids": ["ZAD-7"]}]
    renamed_commit = git_out(vault, "log", "--format=%H", "--grep", "rename tasks ZAD-n to Tn").strip()
    assert renamed_commit == moved["commit"]
    assert git_out(vault, "status", "--porcelain") == ""
    health = run("health", "--vault", str(vault))[1]["issues"]
    assert not health.get("schema") and not health.get("broken_links")

    code, again = run("setup", "apply", "--vault", str(vault))
    assert code == 0 and again["task_ids"] is None


def test_task_rename_keeps_generated_blocks_unedited(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    (vault / "Tasks").mkdir(parents=True)
    (vault / "Notes").mkdir()
    (vault / "Tasks" / "ZAD-1 Write the spec.md").write_text(LEGACY_TASK.format(id="ZAD-1"))
    intact, edited = "See [[ZAD-1 Write the spec]].\n", "Hand-edited, see [[ZAD-1 Write the spec]].\n"
    note = vault / "Notes" / "Design.md"
    note.write_text(
        "---\ntype: note\ncreated: 2026-10-14\nsummary: s\n---\n"
        f"<!-- @generated:intact sha={blocks.digest(intact)} -->\n{intact}<!-- @end -->\n"
        f"<!-- @generated:edited sha={blocks.digest('generated text')} -->\n{edited}<!-- @end -->\n"
    )

    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")

    _, check = run("block", "check", "--file", "Notes/Design.md", vault=vault)
    assert check["blocks"] == [{"name": "intact", "status": "ok"}, {"name": "edited", "status": "edited"}]
    assert note.read_text().count("[[T1 Write the spec]]") == 2


def test_new_task_ids_continue_after_legacy_ones(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    (vault / "Tasks").mkdir(parents=True)
    (vault / "Tasks" / "ZAD-7 Old.md").write_text(LEGACY_TASK.format(id="ZAD-7"))
    code, out = run("note", "next-id", vault=vault)
    assert code == 0 and out["id"] == "T8"


def test_legacy_id_whose_new_id_is_taken_is_left_and_reported(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    (vault / "Tasks").mkdir(parents=True)
    (vault / "Tasks" / "ZAD-3 Old.md").write_text(LEGACY_TASK.format(id="ZAD-3"))
    (vault / "Tasks" / "T3 New.md").write_text(LEGACY_TASK.format(id="T3"))
    _, result = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    assert result["task_ids"]["skipped"] == [{"rel": "Tasks/ZAD-3 Old.md", "reason": "T3 already exists"}]
    assert (vault / "Tasks" / "ZAD-3 Old.md").is_file()


def test_apply_adds_missing_ignore_rules_to_an_existing_gitignore(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    vault.mkdir()
    (vault / ".gitignore").write_text("private/\n.DS_Store")
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    lines = (vault / ".gitignore").read_text().splitlines()
    assert lines[:2] == ["private/", ".DS_Store"]
    assert ".claude/" in lines and lines.count(".DS_Store") == 1

    (vault / ".claude").mkdir()
    (vault / ".claude" / "settings.local.json").write_text("{}")
    _, again = run("setup", "apply", "--vault", str(vault))
    assert again["commit"] is None
    status = subprocess.run(["git", "-C", str(vault), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""


def test_required_plugins_block_ready_until_installed_then_apply_configures_them(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    report = setup_mod.cmd_check(vault)
    plugins = {p["id"]: p for p in report["community_plugins_required"]}
    assert set(plugins) == {"obsidian-git", "obsidian-excalidraw-plugin", "templater-obsidian", "calendar-bases"}
    assert not report["ready"]
    assert not any(p["installed"] or p["enabled"] for p in plugins.values())

    # What Obsidian leaves after installing: the manifest, the enabled list and the plugin's own defaults.
    obsidian = vault / ".obsidian"
    for plugin_id, data in {
        "obsidian-git": {"autoSaveInterval": 0, "disablePush": False, "commitMessage": "my own: {{date}}"},
        "obsidian-excalidraw-plugin": {"folder": "Excalidraw", "compress": True, "theme": "dark"},
        "templater-obsidian": {
            "templates_folder": "",
            "enabled_templates_hotkeys": ["Mine.md", "Templates/Generated/Gone.md"],
            "ignore_folders_on_creation": [{"folder": "Private"}],
        },
    }.items():
        (obsidian / "plugins" / plugin_id).mkdir(parents=True)
        (obsidian / "plugins" / plugin_id / "manifest.json").write_text(json.dumps({"id": plugin_id, "version": "1"}))
        (obsidian / "plugins" / plugin_id / "data.json").write_text(json.dumps(data))
    # Calendar Bases keeps its options in the .base views: no data.json, and synapsidian writes none.
    (obsidian / "plugins/calendar-bases").mkdir()
    (obsidian / "plugins/calendar-bases/manifest.json").write_text(json.dumps({"id": "calendar-bases"}))
    (obsidian / "community-plugins.json").write_text(json.dumps(list(setup_mod.REQUIRED_PLUGINS)))
    assert {k for p in setup_mod.plugins_status(vault) for k in p["settings_unset"]} >= {"autoSaveInterval", "folder"}

    _, applied = run("setup", "apply", "--vault", str(vault))
    git = json.loads((obsidian / "plugins/obsidian-git/data.json").read_text())
    drawing = json.loads((obsidian / "plugins/obsidian-excalidraw-plugin/data.json").read_text())
    assert git["autoSaveInterval"] == 30 and git["disablePush"] is True
    assert git["commitMessage"] == "my own: {{date}}"  # the user's choice is kept and reported
    assert any("commitMessage" in k for k in applied["kept_user_settings"])
    assert drawing == {"folder": "Attachments", "compress": False, "theme": "dark"}
    templater = json.loads((obsidian / "plugins/templater-obsidian/data.json").read_text())
    assert templater["templates_folder"] == "Templates/Generated"
    # The user's entries stay; synapsidian adds a command per generated template and drops one it no longer ships.
    hotkeys = templater["enabled_templates_hotkeys"]
    assert (
        hotkeys[0] == "Mine.md"
        and "Templates/Generated/Task.md" in hotkeys
        and "Templates/Generated/Gone.md" not in hotkeys
    )
    ignored = [e["folder"] for e in templater["ignore_folders_on_creation"]]
    assert ignored[0] == "Private" and {"Inbox", "Sources", "Tasks", "Daily"} <= set(ignored)
    assert "Templates" not in ignored
    assert sorted(applied["plugins_configured"]) == ["obsidian-excalidraw-plugin", "obsidian-git", "templater-obsidian"]
    assert not (obsidian / "plugins/calendar-bases/data.json").exists()

    plugins = {p["id"]: p for p in setup_mod.plugins_status(vault)}
    assert all(p["installed"] and p["enabled"] and not p["settings_unset"] for p in plugins.values())
    _, again = run("setup", "apply", "--vault", str(vault))
    assert again["plugins_configured"] == [] and again["commit"] is None


def test_addon_plugins_are_required_with_its_extension_and_recommended_ones_never_block_ready(run, projects_vault):
    run("setup", "apply", "--vault", str(projects_vault))
    plugins = {p["id"]: p for p in setup_mod.plugins_status(projects_vault)}
    assert plugins["folder-notes"]["required_by"] == "synapsidian-projects"
    assert plugins["excalidraw-extras"]["required_by"] == "synapsidian-projects"  # D154: Mermaid into drawings
    assert plugins["calendar-bases"]["required_by"] == "synapsidian"

    obsidian = projects_vault / ".obsidian"
    for plugin_id in [*setup_mod.required_plugins(projects_vault), *setup_mod.RECOMMENDED_PLUGINS]:
        (obsidian / "plugins" / plugin_id).mkdir(parents=True)
        (obsidian / "plugins" / plugin_id / "manifest.json").write_text(json.dumps({"id": plugin_id, "version": "1"}))
    (obsidian / "community-plugins.json").write_text(json.dumps(list(setup_mod.required_plugins(projects_vault))))
    run("setup", "apply", "--vault", str(projects_vault))
    report = setup_mod.cmd_check(projects_vault)
    assert all(p["installed"] and p["enabled"] for p in report["community_plugins_required"])
    # Claudian is installed but not enabled: offered, never waited for.
    assert report["community_plugins_recommended"] == [
        {"id": "realclaudian", "name": "Claudian", "installed": True, "version": "1", "enabled": False}
    ]
    assert not any(p["installed"] for p in setup_mod.plugins_status(projects_vault.parent / "none"))


def test_shipped_calendar_views_start_on_a_date_field_of_their_type():
    s = schema.load(None)
    calendars = {}
    for base in sorted(setup_mod.config.BASES_DIR.glob("*.base")):
        text = base.read_text()
        note_type = re.search(r'note\.type == "(\w+)"', text).group(1)
        for view in yaml.safe_load(text)["views"]:
            if view["type"] == "calendar":
                field = view["startDate"].removeprefix("note.")
                assert s.fields_for(note_type)[field].kind == "date", base.name
                calendars[note_type] = field
    assert calendars == {"goal": "target", "meeting": "date", "task": "due"}


def test_excalidraw_drawings_are_not_notes(run, vault):
    drawing = vault / "Notes/Flow.excalidraw.md"  # a drawing kept outside Attachments/
    drawing.parent.mkdir()
    drawing.write_text("---\nexcalidraw-plugin: parsed\n---\n# Text Elements\nstart\n")
    _, out = run("health", "--today", "2026-10-14", vault=vault)
    assert "Flow" not in json.dumps(out["issues"])
    _, hook = run("validate", "--hook", vault=vault, stdin=json.dumps({"tool_input": {"file_path": str(drawing)}}))
    assert hook is None  # the write hook stays silent


def test_daily_template_matches_the_daily_schema(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    template = (vault / "Templates" / "Daily.md").read_text()
    assert template.startswith("---\ntype: daily\n")
    for block in ("brief", "agenda", "devlog", "overnight"):
        assert f"<!-- @generated:{block} -->" in template


def test_property_types_are_consistent_across_note_types(fixture_vault):
    types = setup_mod.property_types(schema.load(fixture_vault))  # core plus both add-ons
    assert types["due"] == "date" and types["attendees"] == "multitext" and "tags" not in types
    assert types["scanned_at"] == "date" and types["manager"] == "text" and types["number"] == "number"


@pytest.fixture
def fake_registry(tmp_path, monkeypatch):
    registry = tmp_path / "obsidian" / "obsidian.json"
    registry.parent.mkdir()  # Obsidian's folder exists once it has run, so it counts as installed
    host = setup_mod.obsidian_host("linux", {}, tmp_path)
    monkeypatch.setattr(setup_mod, "HOST", replace(host, apps=(), support=registry.parent))
    return registry


@pytest.mark.parametrize(
    ("platform", "env", "support", "opener"),
    [
        ("darwin", {}, "Library/Application Support/obsidian", "open 'obsidian://x'"),
        ("win32", {"APPDATA": "{home}/Roaming"}, "Roaming/obsidian", 'start "" "obsidian://x"'),
        ("win32", {}, "AppData/Roaming/obsidian", 'start "" "obsidian://x"'),
        ("linux", {}, ".config/obsidian", "xdg-open 'obsidian://x'"),
        ("linux", {"XDG_CONFIG_HOME": "{home}/xdg"}, "xdg/obsidian", "xdg-open 'obsidian://x'"),
        ("freebsd14", {}, ".config/obsidian", "xdg-open 'obsidian://x'"),
    ],
)
def test_obsidian_host_follows_the_platform(tmp_path, platform, env, support, opener):
    host = setup_mod.obsidian_host(platform, {k: v.format(home=tmp_path) for k, v in env.items()}, tmp_path)
    assert host.registry == tmp_path / support / "obsidian.json"
    assert host.open_command("obsidian://x") == opener
    assert ("brew" in host.install) == (platform == "darwin")
    assert ("Cmd+Q" in host.quit) == (platform == "darwin")


def test_obsidian_host_finds_the_flatpak_config_only_when_no_native_one(tmp_path):
    flatpak = tmp_path / ".var" / "app" / "md.obsidian.Obsidian" / "config" / "obsidian"
    flatpak.mkdir(parents=True)
    assert setup_mod.obsidian_host("linux", {}, tmp_path).support == flatpak
    (tmp_path / ".config" / "obsidian").mkdir(parents=True)
    assert setup_mod.obsidian_host("linux", {}, tmp_path).support == tmp_path / ".config" / "obsidian"


def test_status_reads_the_version_from_updates_and_leaves_an_unknown_one_open(fake_registry, monkeypatch):
    monkeypatch.setattr(setup_mod, "obsidian_running", lambda: False)
    status = setup_mod.obsidian_status()
    assert status["installed"] and status["app_version"] is None and status["version_ok"] is None
    for version in ("1.9.10", "1.14.2"):
        (fake_registry.parent / f"obsidian-{version}.asar").touch()
    status = setup_mod.obsidian_status()
    assert status["app_version"] == "1.14.2" and status["version_ok"] is True
    assert status["registry"] == str(fake_registry) and "flatpak" in status["install"]


def test_register_off_macos_reaches_the_registry(fake_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "obsidian_running", lambda: False)
    vault = tmp_path / "My Synapsidian"
    vault.mkdir()
    result = setup_mod.cmd_register(vault)
    assert result["registered"] and result["open_with"] == "xdg-open 'obsidian://open?vault=My%20Synapsidian'"


def test_register_says_how_to_install_when_obsidian_never_ran(fake_registry, tmp_path):
    fake_registry.parent.rmdir()
    result = setup_mod.cmd_register(tmp_path)
    assert not result["ok"] and "never been opened" in result["error"] and "flatpak" in result["install"]


def test_register_refuses_while_obsidian_runs(fake_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "obsidian_running", lambda: True)
    for closed in (False, True):  # the user's word doesn't override what synapsidian sees
        result = setup_mod.cmd_register(tmp_path, obsidian_closed=closed)
        assert not result["ok"] and "is running" in result["error"]
    assert not fake_registry.exists()


def test_register_needs_the_users_word_where_it_cannot_check(fake_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "obsidian_running", lambda: None)
    result = setup_mod.cmd_register(tmp_path)
    assert not result["ok"] and result["running"] is None and "--obsidian-closed" in result["error"]
    assert not fake_registry.exists()
    assert setup_mod.cmd_register(tmp_path, obsidian_closed=True)["registered"]


@pytest.mark.parametrize(
    ("platform", "outcome", "expected"),
    [
        ("darwin", subprocess.CompletedProcess([], 0), True),
        ("linux", subprocess.CompletedProcess([], 1), False),
        ("linux", subprocess.CompletedProcess([], 3), None),
        ("linux", FileNotFoundError("pgrep"), None),
        ("win32", subprocess.CompletedProcess([], 0, '"Obsidian.exe","4242"\n'), True),
        ("win32", subprocess.CompletedProcess([], 0, "INFO: No tasks are running.\n"), False),
    ],
)
def test_obsidian_running_per_platform(tmp_path, monkeypatch, platform, outcome, expected):
    calls = []

    def fake_run(cmd, **_):
        calls.append(cmd)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(setup_mod, "HOST", setup_mod.obsidian_host(platform, {}, tmp_path))
    monkeypatch.setattr(setup_mod.subprocess, "run", fake_run)
    assert setup_mod.obsidian_running() is expected
    assert calls[0][0] == ("tasklist" if platform == "win32" else "pgrep")
    if platform != "win32":
        assert calls[0][-1] == ("Obsidian" if platform == "darwin" else "obsidian")


def test_register_backs_up_and_adds_the_vault_once(fake_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(setup_mod, "obsidian_running", lambda: False)
    fake_registry.write_text(json.dumps({"vaults": {"aaaa": {"path": "/old", "ts": 1, "open": True}}, "cli": True}))
    vault = tmp_path / "Synapsidian"
    vault.mkdir()

    result = setup_mod.cmd_register(vault)
    assert result["registered"] and Path(result["backup"]).exists()
    data = json.loads(fake_registry.read_text())
    assert data["cli"] is True and "open" not in data["vaults"]["aaaa"]
    assert [v["path"] for v in data["vaults"].values()] == ["/old", str(vault)]

    assert setup_mod.cmd_register(vault)["registered"] is False


def test_check_reports_automation_and_queue(run, vault):
    queue = vault / ".git" / "synapsidian" / "session-queue.jsonl"
    queue.parent.mkdir()
    queue.write_text(json.dumps({"session_id": "s1", "date": "2026-10-13", "transcript_path": None}) + "\n")
    _, report = run("setup", "check", "--vault", str(vault))
    automation = report["automation"]
    assert automation["ok"] and {"SessionEnd", "SessionStart"} <= set(automation["hook_events"])
    assert automation["queue"] == {"rows": 1, "pending_days": {"2026-10-13": 1}}
    assert automation["session_end_json_tool"] in {"jq", "python3"}


def test_check_flags_missing_tools_and_blocks_ready(run, vault, monkeypatch):
    monkeypatch.setattr(setup_mod, "find_uv", lambda: None)
    monkeypatch.setattr(setup_mod.shutil, "which", lambda name: None)
    status = setup_mod.automation_status(vault)
    assert not status["ok"] and len(status["problems"]) == 2
    assert not setup_mod.cmd_check(vault)["ready"]


def test_selftest_drives_the_session_hooks(run, fixture_vault):
    subprocess.run(["git", "init", "-q", str(fixture_vault)], check=True)
    code, result = run("setup", "selftest", "--vault", str(fixture_vault))
    assert code == 0 and result["ok"], result
    assert result["checks"][0]["check"] == "SessionEnd queues a row"
    assert not (fixture_vault / ".git" / "synapsidian" / "session-queue.jsonl").exists()  # the real queue stays clean


def test_core_vault_knows_no_work_types(run, vault):
    _, where = run("note", "--vault", str(vault), "where")
    assert where["extensions"] == [] and "options" not in where
    for work_type in ("architecture", "win"):
        code, out = run("note", "new", "--type", work_type, "--title", "x", vault=vault)
        assert code == 2 and "unknown type" in out["error"]
    code, out = run(
        "note", "new", "--type", "meeting", "--title", "x", "--field", "kind=1-1", "--field", "summary=s", vault=vault
    )
    assert code == 2 and "kind" in out["error"]


def test_extension_install_adds_types_folders_and_bases_in_one_commit(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    code, out = run("setup", "extension", "--vault", str(vault), "--from", str(WORK / "extension"))
    assert code == 0 and out["commit"] and out["extension"] == "synapsidian-work", out
    assert (vault / ".synapsidian/extensions/synapsidian-work/schema.yaml").is_file()
    assert (vault / "Bases/One-to-ones.base").is_file() and not (vault / "Architecture").exists()
    assert (vault / "Bases/Wins.base").is_file() and (vault / "Wins").is_dir()
    assert "manager" in json.loads((vault / ".obsidian/types.json").read_text())["types"]
    tracked = subprocess.run(
        ["git", "-C", str(vault), "ls-files", ".synapsidian"], capture_output=True, text=True
    ).stdout
    assert ".synapsidian/extensions/synapsidian-work/templates/meeting-1-1.md" in tracked
    assert (vault / "Templates/Generated/Meeting - 1-1.md").is_file()  # the add-on's kinds get templates too
    assert {
        "Templates/Generated/Meeting - 1-1.md",
        "Templates/Generated/Meeting - Retro.md",
        "Templates/Generated/Win.md",
    } <= set(out["created"])

    _, where = run("note", "--vault", str(vault), "where")
    assert where["extensions"] == ["synapsidian-work"]
    code, note = run(
        "note",
        "new",
        "--type",
        "meeting",
        "--title",
        "Alex",
        "--field",
        "kind=1-1",
        "--field",
        "date=2026-10-19",
        "--field",
        "summary=s",
        vault=vault,
    )
    assert code == 0 and "## Talking points" in (vault / note["rel"]).read_text()

    code, again = run("setup", "extension", "--vault", str(vault), "--from", str(WORK / "extension"))
    assert code == 0 and again["commit"] is None  # unchanged: no second commit


def test_extension_may_only_widen_core_fields(tmp_path):
    raw = {"types": {"task": {"fields": {"status": {"kind": "text", "enum": ["todo"]}}}}}
    schema.merge_extension(raw, {"extend": {"task": {"fields": {"status": {"enum": ["todo", "later"]}}}}}, "x")
    assert raw["types"]["task"]["fields"]["status"]["enum"] == ["todo", "later"]
    with pytest.raises(ValueError, match="only its enum"):
        schema.merge_extension(raw, {"extend": {"task": {"fields": {"status": {"required": True}}}}}, "x")
    with pytest.raises(ValueError, match="already exists"):
        schema.merge_extension(raw, {"types": {"task": {}}}, "x")
    # Two add-ons defining one type (a type moving between them): the first keeps it, no error.
    both = {"types": {"task": {}}}
    warnings = schema.merge_extensions(both, [("a", {"types": {"map": {"folder": "A"}}}),
                                              ("b", {"types": {"map": {"folder": "B"}}})])  # fmt: skip
    assert both["types"]["map"] == {"folder": "A"}
    assert warnings == ["extension b: type 'map' is also defined by a, whose definition is used; skipped"]
    # A type nobody defines is skipped with a warning, so an outdated extension can't break the vault.
    assert schema.merge_extension(raw, {"extend": {"nope": {}}}, "x") == [
        "extension x: extends type 'nope', which no installed schema defines; skipped"
    ]


def test_conflicting_extension_is_refused_before_any_write(run, vault, tmp_path):
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "extension.yaml").write_text("name: bad\nversion: 0.0.1\n")
    (bad / "schema.yaml").write_text("types:\n  task: {folder: Tasks, filename: '{title}'}\n")
    code, out = run("setup", "extension", "--vault", str(vault), "--from", str(bad))
    assert code == 1 and "already exists" in out["error"]
    assert not (vault / ".synapsidian" / "extensions").exists()


# --- About sections and the interview (D160) ----------------------------------------------------


def sections_of(text: str) -> list[str]:
    return re.findall(r"^#{2,3} .+$", text, flags=re.M)


def test_apply_adds_declared_about_sections_ahead_of_rules_and_keeps_the_users_text(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    vault.mkdir()
    old = "---\ntype: about\nrole: Engineer\n---\n## Who I am\nMe, in my words.\n\n## How I work\nSlowly.\n"
    (vault / "About.md").write_text(old)
    _, first = run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    text = (vault / "About.md").read_text()
    assert "About.md" in first["updated"]
    assert "## Who I am\nMe, in my words.\n" in text and "## How I work\nSlowly.\n" in text
    assert sections_of(text).index("## Current focus") < sections_of(text).index("## Rules")
    assert sections_of(text)[-1] == "## Rules"
    _, second = run("setup", "apply", "--vault", str(vault))
    assert "About.md" not in second["updated"] and (vault / "About.md").read_text() == text


def test_extension_install_adds_its_sections_and_subsections(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    assert "## Work" not in (vault / "About.md").read_text()
    code, out = run("setup", "extension", "--vault", str(vault), "--from", str(WORK / "extension"))
    assert code == 0 and "About.md" in out["updated"]
    text = (vault / "About.md").read_text()
    assert sections_of(text).index("### Work") == sections_of(text).index("## Current focus") + 1
    assert sections_of(text)[-2:] == ["## Work", "## Rules"]


def test_apply_moves_working_hours_into_how_i_work_without_the_work_addon(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    vault.mkdir()
    (vault / "About.md").write_text("---\ntype: about\nrole: Engineer\nworking_hours: 9-17\n---\n## How I work\n")
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x")
    text = (vault / "About.md").read_text()
    assert "working_hours" not in text and "- Working hours: 9-17" in text and "role: Engineer" in text
    run("setup", "extension", "--vault", str(vault), "--from", str(WORK / "extension"))
    (vault / "About.md").write_text(text.replace("role: Engineer\n", "role: Engineer\nworking_hours: 8-16\n"))
    run("setup", "apply", "--vault", str(vault))
    assert "working_hours: 8-16" in (vault / "About.md").read_text()  # a field of the installed schema stays


def test_setup_about_lists_what_is_empty_per_owner(run, tmp_path):
    vault = tmp_path / "Synapsidian"
    run("setup", "apply", "--vault", str(vault), "--name", "N", "--email", "e@x", "--about", "role=Engineer")
    run("setup", "extension", "--vault", str(vault), "--from", str(WORK / "extension"))
    code, out = run("setup", "about", "--vault", str(vault))
    assert code == 0 and out["owners"] == ["synapsidian", "synapsidian-work"]
    ask = {(q["owner"], q["section"], q["subsection"]): q["state"] for q in out["questions"]}
    assert ask == {
        ("synapsidian", "Who I am", None): "empty",
        ("synapsidian", "Current focus", None): "empty",
        ("synapsidian", "How I work", None): "empty",
        ("synapsidian-work", "Work", None): "empty",
        ("synapsidian-work", "Current focus", "Work"): "empty",
    }
    fields = {f["name"]: (f["owner"], f["empty"]) for f in out["fields"]}
    assert fields["role"] == ("synapsidian", False) and fields["language"] == ("synapsidian", True)
    assert fields["team"] == ("synapsidian-work", True) and fields["working_hours"] == ("synapsidian-work", True)

    filled = run("note", "fill", "--file", "About.md", "--section", "Who I am", stdin="Me.\n", vault=vault)
    assert filled[1]["status"] == "filled", filled
    _, core = run("setup", "about", "--vault", str(vault), "--owner", "synapsidian")
    assert {q["owner"] for q in core["questions"]} == {"synapsidian"}
    assert {q["section"]: q["state"] for q in core["questions"]}["Who I am"] == "filled"
    assert run("setup", "about", "--vault", str(tmp_path / "none"))[0] != 0
