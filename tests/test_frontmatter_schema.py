from __future__ import annotations

import datetime as dt

import pytest
import yaml

from conftest import PROJECTS, WORK
from synapsidianlib import frontmatter, schema


def test_parse_handles_bom_crlf_and_missing_block():
    parsed = frontmatter.parse("﻿---\r\ntype: note\r\n---\r\nBody\r\n")
    assert parsed.meta == {"type": "note"}
    assert parsed.body == "Body\n"
    assert frontmatter.parse("No frontmatter").meta is None


def test_parse_reports_unclosed_and_invalid_yaml():
    assert frontmatter.parse("---\ntype: note\n").error == "frontmatter has no closing ---"
    assert "not valid YAML" in frontmatter.parse("---\ntype: [\n---\n").error
    assert "mapping" in frontmatter.parse("---\n- a\n---\n").error


def test_dump_round_trips_dates_and_quotes_links():
    text = frontmatter.dump({"type": "task", "due": dt.date(2026, 10, 15), "project": "[[X]]"}, "## Context\n")
    assert "due: 2026-10-15\n" in text
    assert "project: '[[X]]'\n" in text
    assert frontmatter.parse(text).meta["due"] == dt.date(2026, 10, 15)


def test_link_fields_take_notes_or_urls():
    f = schema.load().fields_for("task")["source_link"]
    thread = "https://mail.google.com/mail/#all/thread-f:1878928180921078667"
    assert schema.coerce(f, thread) == thread and schema.check(f, thread) is None
    assert schema.coerce(f, "2026-10-14") == "[[2026-10-14]]"
    assert schema.check(f, "plain text") is not None


def test_links_keep_commas_inside_wikilinks_and_urls_beside_them():
    f = schema.load().fields_for("meeting")["attendees"]
    assert schema.coerce(f, "[[A]],[[B, Jr.]], https://example.com/x,C,") == [
        "[[A]]", "[[B, Jr.]]", "https://example.com/x", "[[C]]",
    ]  # fmt: skip
    # A space after the comma, before a wikilink with commas in it, keeps it whole too.
    assert schema.coerce(f, "[[A]], [[B (x, y, z) and c]] ,  C, [[D]] [[E]]") == [
        "[[A]]", "[[B (x, y, z) and c]]", "[[C]]", "[[D]]", "[[E]]",
    ]  # fmt: skip
    assert schema.check(f, ["[[A]]", "https://example.com/x"]) is None
    assert schema.check(f, ["[[A]]", "plain text"]) is not None


def test_dump_never_writes_yaml_aliases():
    today = dt.date(2026, 10, 13)
    text = frontmatter.dump({"created": today, "fetched_at": today, "tags": (tags := ["a"]), "aliases": tags}, "")
    assert "&id" not in text and "*id" not in text
    assert "fetched_at: 2026-10-13\n" in text


def test_every_type_and_kind_has_a_template_and_a_formattable_filename(fixture_vault):
    s = schema.load(fixture_vault)  # core plus both add-ons
    assert {"project", "spec", "change", "architecture", "meeting"} <= set(s.types)
    now = dt.datetime(2026, 10, 13, 9, 5)
    for note_type in s.types.values():
        kinds = s.fields_for(note_type.name).get("kind")
        for kind in (kinds.enum if kinds else ()) or (None,):
            assert note_type.template(kind) is not None, (note_type.name, kind)
            name = schema.filename_for(note_type, {"id": "T1", "kind": kind}, "Some title", now)
            assert schema.filename_problem(name) is None, (note_type.name, name)


def test_validate_flags_missing_enum_link_and_folder():
    issues = schema.validate(
        {
            "type": "task",
            "created": "2026-10-13",
            "summary": "x",
            "id": "T1",
            "status": "maybe",
            "priority": "high",
            "source_link": "Not a link",
        },
        "Notes/T1 x.md",
    )
    text = " | ".join(issues)
    assert "`status` is 'maybe'" in text
    assert "`source_link` should be a quoted wikilink" in text
    assert "belongs in Tasks/" in text


def test_validate_accepts_a_correct_note_and_archived_location():
    meta = {"type": "idea", "created": dt.date(2026, 10, 1), "summary": "x", "status": "new"}
    assert schema.validate(meta, "Ideas/2026-10-01 x.md") == []
    assert schema.validate(meta, "Archive/Ideas/2026-10-01 x.md") == []


def test_summary_is_optional_only_where_the_schema_says():
    assert (
        schema.validate({"type": "daily", "created": "2026-10-13", "date": "2026-10-13"}, "Daily/2026-10-13.md") == []
    )
    assert any("summary" in i for i in schema.validate({"type": "note", "created": "2026-10-13"}, "Notes/x.md"))


def test_clean_title_strips_characters_links_cannot_hold():
    assert schema.clean_title("Fix: rounding / pay gap?") == "Fix rounding pay gap"
    assert schema.filename_problem("a#b") is not None


def write_extension(vault, name: str, text: str) -> None:
    folder = vault / ".synapsidian" / "extensions" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "schema.yaml").write_text(text, encoding="utf-8")


PROJECT_FOLDERS = """\
extend:
  task:
    fields:
      project: {kind: link}
    folder_by: {field: project, folder: "Projects/{project}/Tasks"}
  research:
    fields:
      project: {kind: link}
    folder_by: {field: project, folder: "Projects/{project}/Research"}
"""


def test_folder_by_puts_a_note_under_the_linked_note_and_keeps_the_flat_folder_valid(tmp_path):
    write_extension(tmp_path, "projects", PROJECT_FOLDERS)
    s = schema.load(tmp_path)
    task, research = s.types["task"], s.types["research"]  # research got its field in the same block
    assert task.folder_for({"project": "[[Alpha]]"}) == "Projects/Alpha/Tasks"
    assert task.folder_for({"project": "[[Alpha#Goal|the app]]"}) == "Projects/Alpha/Tasks"
    assert task.folder_for({"project": "https://example.com/board"}) == "Tasks"  # a URL names no note
    assert task.folder_for({}) == "Tasks"
    assert research.folder_for({"project": "[[Alpha]]"}) == "Projects/Alpha/Research"

    meta = {"type": "task", "created": "2026-10-28", "summary": "s", "id": "T1", "status": "todo",
            "priority": "low", "project": "[[Alpha]]"}  # fmt: skip
    assert schema.validate(meta, "Projects/Alpha/Tasks/T1 x.md", s) == []
    assert schema.validate(meta, "Tasks/T1 x.md", s) == []  # written before the project folders existed
    assert schema.validate(meta, "Archive/Projects/Alpha/Tasks/T1 x.md", s) == []
    wrong = " | ".join(schema.validate(meta, "Projects/Beta/Tasks/T1 x.md", s))
    assert "belongs in Projects/Alpha/Tasks/ (or Tasks/)" in wrong
    assert schema.validate({**meta, "project": None}, "Projects/Alpha/Tasks/T1 x.md", s)  # no project, no nesting


def test_folder_by_rejects_what_it_cannot_resolve(tmp_path):
    with_field = "extend:\n  task:\n    fields:\n      project: {kind: link}\n"
    cases = {
        "not a link field": "extend:\n  task:\n    folder_by: {field: priority, folder: 'P/{priority}'}\n",
        "other placeholder": with_field + "    folder_by: {field: project, folder: 'P/{project}/{id}'}\n",
        "no placeholder": with_field + "    folder_by: {field: project, folder: 'Projects'}\n",
        "unknown extend key": "extend:\n  task:\n    folder: Elsewhere\n",
        "folder placeholder other than title": "types:\n  thing: {folder: 'Things/{id}', filename: '{title}'}\n",
    }
    for i, (case, text) in enumerate(cases.items()):
        root = tmp_path / str(i)
        write_extension(root, "bad", text)
        try:
            schema.load(root)
        except ValueError:
            continue
        raise AssertionError(f"{case}: loaded without error")

    root = tmp_path / "two"
    write_extension(root, "a-projects", PROJECT_FOLDERS)
    write_extension(root, "b-other", "extend:\n  task:\n    folder_by: {field: project, folder: 'X/{project}'}\n")
    try:
        schema.load(root)
    except ValueError as exc:
        assert "already has a folder_by" in str(exc)
    else:
        raise AssertionError("a second folder_by for one type loaded")


def test_one_add_on_may_widen_another_whatever_their_names_and_a_missing_one_only_warns(tmp_path):
    defines = "types:\n  gadget: {folder: Gadgets, filename: '{title}', fields: {size: {kind: text}}}\n"
    widens = "extend:\n  gadget:\n    fields:\n      colour: {kind: text}\n"
    write_extension(tmp_path, "a-widens", widens)  # sorts first, so a one-pass merge would fail
    write_extension(tmp_path, "b-defines", defines)
    s = schema.load(tmp_path)
    assert {"size", "colour"} <= set(s.types["gadget"].fields) and s.warnings == ()

    alone = tmp_path / "alone"
    write_extension(alone, "a-widens", widens)
    s = schema.load(alone)  # the defining add-on isn't installed: skipped, never fatal
    assert "gadget" not in s.types
    assert s.warnings == ("extension a-widens: extends type 'gadget', which no installed schema defines; skipped",)

    # An extension written for an older core files tasks by a field the core no longer has.
    old = tmp_path / "old"
    write_extension(old, "projects", "extend:\n  task:\n    folder_by: {field: project, folder: 'P/{project}'}\n")
    s = schema.load(old)
    assert s.types["task"].folder_by is None
    assert s.warnings == ("task.folder_by: no field 'project' to file by; skipped",)


def test_a_title_folder_gives_each_note_its_own_and_keeps_its_fixed_part_valid(tmp_path):
    write_extension(tmp_path, "hubs", "types:\n  hub: {folder: 'Hubs/{title}', filename: '{title}'}\n")
    hub = schema.load(tmp_path).types["hub"]
    assert hub.folder_prefix == "Hubs" and hub.folder_for({}, "Alpha: one") == "Hubs/Alpha one"
    meta = {"type": "hub", "created": "2026-10-28", "summary": "s"}
    s = schema.load(tmp_path)
    assert schema.validate(meta, "Hubs/Alpha/Alpha.md", s) == []
    assert schema.validate(meta, "Hubs/Alpha.md", s) == []  # written before hubs had folders
    assert "belongs in Hubs/Alpha/" in " ".join(schema.validate(meta, "Hubs/Beta/Alpha.md", s))


def test_fixture_vault_is_schema_valid(fixture_vault):
    from synapsidianlib import vault

    s = schema.load(fixture_vault)
    problems = {n.rel: schema.validate(n.meta, n.rel, s) for n in vault.iter_notes(fixture_vault)}
    assert {k: v for k, v in problems.items() if v} == {}


def test_extension_sections_add_a_section_or_a_subsection_of_one(tmp_path):
    raw = {"types": {"about": {"fields": {}, "sections": [{"title": "Who I am", "ask": "Who?"}]}}}
    warnings = schema.merge_extensions(
        raw,
        [
            (
                "x",
                {
                    "extend": {
                        "about": {
                            "sections": [
                                {"title": "Work", "ask": "What?"},
                                {"title": "Who I am", "subsection": "Work", "ask": "Where?"},
                                {"title": "Gone", "subsection": "Y", "ask": "Never."},
                            ]
                        }
                    }
                },
            )
        ],
    )
    assert [(s["title"], s.get("subsection"), s.get("owner")) for s in raw["types"]["about"]["sections"]] == [
        ("Who I am", None, None),
        ("Work", None, "x"),
        ("Who I am", "Work", "x"),
    ]
    assert warnings == ["extension x: about section 'Gone' to add 'Y' to isn't defined; skipped"]
    with pytest.raises(ValueError, match="add a `subsection:`"):
        schema.merge_extension(raw, {"extend": {"about": {"sections": [{"title": "work", "ask": "Dup?"}]}}}, "y")
    with pytest.raises(ValueError, match="already has a subsection"):
        schema.merge_extension(
            raw, {"extend": {"about": {"sections": [{"title": "Who I am", "subsection": "work", "ask": "Dup?"}]}}}, "y"
        )
    with pytest.raises(ValueError, match="only about has them"):
        schema.merge_extension({"types": {"task": {}}}, {"extend": {"task": {"sections": []}}}, "y")


def test_installed_schema_records_who_declared_each_about_field_and_section(work_vault, projects_vault):
    # Both fixtures share one vault; extensions merge in name order, so Projects comes before Work.
    about = schema.load(work_vault).types["about"]
    assert about.fields["team"].owner == "synapsidian-work" and about.fields["role"].owner == "synapsidian"
    assert [(x.title, x.subsection, x.owner) for x in about.sections] == [
        ("Who I am", None, "synapsidian"),
        ("Current focus", None, "synapsidian"),
        ("How I work", None, "synapsidian"),
        ("Projects", None, "synapsidian-projects"),
        ("Work", None, "synapsidian-work"),
        ("Current focus", "Work", "synapsidian-work"),
    ]
    assert "working_hours" not in schema.load(None).types["about"].fields


# --- An extension for a newer core (D161) ------------------------------------------------------


def write_manifest(vault, name: str, text: str) -> None:
    (vault / ".synapsidian" / "extensions" / name / "extension.yaml").write_text(text, encoding="utf-8")


def test_an_extension_for_a_newer_core_says_to_update_synapsidian_before_the_merge_fails(tmp_path):
    # A key this core can't read, as synapsidian-projects 0.13.0 was for core 0.33.1.
    write_extension(tmp_path, "projects", "extend:\n  task:\n    lanes: [a, b]\n")
    write_manifest(tmp_path, "projects", "name: projects\nversion: 9.1.0\nrequires: synapsidian >= 99.0.0\n")
    with pytest.raises(schema.SchemaError) as raised:
        schema.load(tmp_path)
    assert str(raised.value).startswith("extension projects 9.1.0 needs synapsidian >= 99.0.0, this is 0.")
    assert str(raised.value).endswith("; update the synapsidian plugin")


def test_a_satisfied_or_missing_requires_loads_and_a_malformed_one_is_refused(tmp_path):
    write_extension(tmp_path, "projects", PROJECT_FOLDERS)
    write_manifest(tmp_path, "projects", "name: projects\nrequires: synapsidian >= 0.1\n")
    assert schema.load(tmp_path).extensions == ("projects",)
    write_manifest(tmp_path, "projects", "name: projects\n")
    assert schema.load(tmp_path).extensions == ("projects",)
    write_manifest(tmp_path, "projects", "name: projects\nrequires: synapsidian 1.0\n")
    with pytest.raises(schema.SchemaError, match="must read `synapsidian >= X"):
        schema.load(tmp_path)


def test_every_load_failure_is_a_schema_error_and_unknown_extend_keys_stay_errors(tmp_path):
    write_extension(tmp_path, "typo", "extend:\n  task:\n    feilds: {}\n")
    with pytest.raises(schema.SchemaError, match="extend: task can't set feilds"):
        schema.load(tmp_path)
    write_extension(tmp_path / "yaml", "broken", "extend: [\n")
    with pytest.raises(schema.SchemaError):
        schema.load(tmp_path / "yaml")


def test_the_add_ons_require_the_core_that_reads_their_schema():
    for plugin in (PROJECTS, WORK):
        manifest = yaml.safe_load((plugin / "extension" / "extension.yaml").read_text())
        assert manifest["requires"] == "synapsidian >= 0.34.0"
        assert schema.requires_problem(manifest, manifest["name"], "0.33.1")
        assert schema.requires_problem(manifest, manifest["name"], "0.34.0") is None
