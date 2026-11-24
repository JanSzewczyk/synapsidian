#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Create notes with schema-correct frontmatter, assign task ids, update fields.

  note.py new   --vault V --type task --title "Review TDD" [--field due=2026-10-17 ...]
  note.py daily --vault V [--date 2026-10-13]
  note.py set   --vault V --file Tasks/T1\\ Review\\ TDD.md --field status=done ...
  note.py next-id --vault V
  note.py where                 print the resolved vault path, its extensions and timezone
  note.py archive --vault V --file Inbox/2026-10-13\\ 0915\\ idea.md
  note.py fill  --vault V --file "Meetings/..." --section Notes [--before "Action items"] < text.md
  note.py section --type person --section "Meetings and tasks"   print that section of the type's template

`fill` writes a `## <section>` only when it is empty or missing (a missing one goes before the
`--before` section, else at the end); a section with any text is kept as it is (`kept`). It
refuses text that looks like a credential.

`new` puts a note in its type's folder, or in its `folder_by` folder when that field is set
(D102), and refuses a file name that another note already has anywhere in the vault. `set` of
that field moves the note and reports `from` and `rel`; commit both paths.

A file name with a date in it (`2026-10-13 Title`) takes the type's `date` field, else
`created`: `--field created=2026-10-13` files a decision under the day it was made, not the day
it was written down (D158). The title then carries no date of its own; one that starts with
a date is refused. `new` and `set` refuse a value that looks like a credential.

Closing a task that has `repeat` (`set --field status=done`) also files the next one and
reports it under `next` (`rel`, `id`, `due`); commit it with the closed task (D124).

Every command prints one JSON object on stdout. Exit 2 = bad input, 3 = file already exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from synapsidianlib import config, frontmatter, gitops, schema, taskids, vault
from synapsidianlib.sections import fill_section, sections
from validate import secret_problems

# A title that repeats the date its file name starts with: `2026-10-13 2026-10-11 Title.md`.
DATED_TITLE = re.compile(r"\d{4}-\d{2}-\d{2}(?!\d)")


def fail(code: int, message: str, **extra: Any) -> None:
    print(json.dumps({"ok": False, "error": message, **extra}))
    sys.exit(code)


def next_task_id(vault_root: Path) -> str:
    """T<n+1>, n the highest task number in the vault (archived tasks and legacy ZAD-n ids included)."""
    tasks = (note for note in vault.iter_notes(vault_root, include_cold=True) if note.type == "task")
    numbers = [n for note in tasks if (n := taskids.task_number(note.get("id"))) is not None]
    return f"T{max(numbers, default=0) + 1}"


def parse_fields(pairs: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            fail(2, f"--field expects key=value, got {pair!r}")
        fields[key.strip()] = value.strip()
    return fields


def build_meta(s: schema.Schema, type_name: str, given: dict[str, str], today: dt.date) -> dict[str, Any]:
    known = s.fields_for(type_name)
    unknown = sorted(set(given) - set(known))
    if unknown:
        fail(2, f"unknown field(s) for {type_name}: {', '.join(unknown)}", allowed=sorted(known))

    meta: dict[str, Any] = {"type": type_name, "created": today}
    for name, f in known.items():
        if name in ("type", "created") and name not in given:
            continue
        raw = given.get(name, f.default)
        if raw is None:
            continue
        try:
            meta[name] = schema.coerce(f, raw)
        except ValueError as exc:
            fail(2, str(exc))
        if problem := schema.check(f, meta[name]):
            fail(2, problem)
    if type_name == "daily":
        meta.setdefault("date", today)
    return meta


def write_new(
    vault_root: Path,
    s: schema.Schema,
    type_name: str,
    title: str,
    meta: dict[str, Any],
    body: str | None,
    now: dt.datetime,
) -> Path:
    note_type = s.types[type_name]
    name = schema.filename_for(note_type, meta, title, now)
    if problem := schema.filename_problem(name):
        fail(2, problem)
    target = vault_root / note_type.folder_for(meta, name) / f"{name}.md"
    if target.exists():
        fail(3, "note already exists", path=str(target), rel=vault.rel_path(vault_root, target))
    # Obsidian resolves [[links]] by file name, so the same name in another folder would make
    # links to either note ambiguous; nested project folders make that possible (D102).
    if same := vault.find_by_stem(vault_root, name):
        fail(3, "a note with that name already exists elsewhere", path=str(same), rel=vault.rel_path(vault_root, same))
    source = note_type.template(meta.get("kind"))
    template = source.read_text(encoding="utf-8") if source else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    # "x" mode: never clobber a file that appeared since the exists() check.
    with target.open("x", encoding="utf-8") as handle:
        handle.write(frontmatter.dump(meta, body if body is not None else template))
    return target


def cmd_new(args: argparse.Namespace, vault_root: Path, s: schema.Schema) -> dict[str, Any]:
    if args.type not in s.types:
        fail(2, f"unknown type {args.type!r}", known=sorted(s.types))
    now = dt.datetime.now()
    given = parse_fields(args.field)
    match args.body_file:
        case None:
            body = None
        case "-":
            body = sys.stdin.read()
        case path:
            body = Path(path).read_text(encoding="utf-8")
    if problems := secret_problems("\n".join([args.title, *given.values(), body or ""])):
        fail(2, "the note looks like it holds a credential; nothing written", problems=problems)
    pattern = s.types[args.type].filename
    # Not a capture (`{date} {time} {title}`): its title is the user's own words, date or not.
    dated = pattern.startswith("{date}") and "{title}" in pattern and "{time}" not in pattern
    if dated and DATED_TITLE.match(args.title.strip()):
        field = "date" if "date" in s.fields_for(args.type) else "created"
        fail(2, f"the file name already starts with the date: drop it from --title and pass --field {field}=YYYY-MM-DD")
    # Two runs filing tasks at once (the evening run and a session) would both read the same
    # highest id: the id is taken and the file written under one lock.
    with gitops.vault_lock(config.state_dir(vault_root), name="notes.lock"):
        if args.type == "task" and "id" not in given:
            given["id"] = next_task_id(vault_root)
        meta = build_meta(s, args.type, given, now.date())
        if s.types[args.type].summary_required and schema.is_empty(meta.get("summary")):
            fail(2, f'type {args.type} needs --field summary="one sentence"')
        fields = s.fields_for(args.type)
        if missing := [n for n, f in fields.items() if f.required and n != "summary" and schema.is_empty(meta.get(n))]:
            fail(2, f"type {args.type} needs {', '.join(f'--field {n}=...' for n in missing)}")
        target = write_new(vault_root, s, args.type, args.title, meta, body, now)
    return {
        "ok": True,
        "path": str(target),
        "rel": vault.rel_path(vault_root, target),
        "id": meta.get("id"),
        "created": True,
    }


def cmd_daily(args: argparse.Namespace, vault_root: Path, s: schema.Schema) -> dict[str, Any]:
    day = schema.as_date(args.date) if args.date else dt.date.today()
    if day is None:
        fail(2, f"--date {args.date!r} is not YYYY-MM-DD")
    note_type = s.types["daily"]
    target = vault_root / note_type.folder / f"{day.isoformat()}.md"
    # Scheduled runs that start together (the morning and the stand-up) both ask for today's note.
    with gitops.vault_lock(config.state_dir(vault_root), name="notes.lock"):
        if target.exists():
            return {"ok": True, "path": str(target), "rel": vault.rel_path(vault_root, target), "created": False}
        meta = build_meta(s, "daily", {"date": day.isoformat(), "created": day.isoformat()}, day)
        target = write_new(vault_root, s, "daily", day.isoformat(), meta, None, dt.datetime.combine(day, dt.time()))
    return {"ok": True, "path": str(target), "rel": vault.rel_path(vault_root, target), "created": True}


def cmd_set(args: argparse.Namespace, vault_root: Path, s: schema.Schema) -> dict[str, Any]:
    target = (vault_root / args.file).resolve()
    if not vault.is_editable_note(vault_root, target, about=True) or not target.is_file():
        fail(2, f"{args.file} is not a note synapsidian may change")
    fields = parse_fields(args.field)
    if vault.rel_path(vault_root, target) == "About.md" and "protected" in fields:
        fail(2, "About.md's protected list is the user's to change, in Obsidian or by hand")
    # Only what this call writes: a note that already holds a hit must stay changeable.
    if problems := secret_problems("\n".join(fields.values())):
        fail(2, "a value looks like it holds a credential; nothing written", problems=problems)
    text = target.read_text(encoding="utf-8")
    parsed = frontmatter.parse(text)
    if parsed.meta is None:
        fail(2, parsed.error or "note has no frontmatter")
    type_name = parsed.meta.get("type")
    known = s.fields_for(type_name) if type_name in s.types else {}
    meta = dict(parsed.meta)
    changed: dict[str, Any] = {}
    for name, raw in fields.items():
        if raw == "":
            if name in meta:
                del meta[name]
                changed[name] = None
            continue
        f = known.get(name)
        if f is None:
            fail(2, f"unknown field {name!r} for type {type_name}", allowed=sorted(known))
        try:
            meta[name] = schema.coerce(f, raw)
        except ValueError as exc:
            fail(2, str(exc))
        if problem := schema.check(f, meta[name]):
            fail(2, problem)
        changed[name] = meta[name] if not hasattr(meta[name], "isoformat") else meta[name].isoformat()
    # Any type with a `done_on` field (a task, an add-on's change) gets the date it was closed.
    closed_now = changed.get("status") == "done" and parsed.meta.get("status") != "done"
    if "done_on" in known and changed.get("status") == "done" and "done_on" not in changed:
        meta["done_on"] = dt.date.today()
        changed["done_on"] = meta["done_on"].isoformat()
    moved_to = _new_home(vault_root, s, type_name, target, meta, changed)
    target.write_text(frontmatter.dump(meta, parsed.body), encoding="utf-8")
    result: dict[str, Any] = {"ok": True, "rel": vault.rel_path(vault_root, target), "changed": changed}
    if moved_to is not None:
        moved_to.parent.mkdir(parents=True, exist_ok=True)
        target.rename(moved_to)
        # Both paths go to `synapsidian commit`: the old one records the move, the new one the note.
        result |= {"rel": vault.rel_path(vault_root, moved_to), "from": result["rel"]}
    if type_name == "task" and closed_now and meta.get("repeat"):
        result["next"] = file_next_occurrence(vault_root, s, meta, Path(result["rel"]).stem)
    return result


REPEAT = re.compile(r"([1-9][0-9]*)([dwmy])")
# `blocked_by` names what had to happen before this occurrence (D144), not before the next one.
NOT_CARRIED = {"type", "created", "id", "status", "due", "done_on", "source", "source_link", "blocked_by"}


def add_interval(day: dt.date, repeat: str) -> dt.date:
    """`day` moved on by a `repeat` interval; a month or year step keeps the day of the month,
    or the month's last day when it is shorter (31 Jan + 1m = 28 or 29 Feb)."""
    match = REPEAT.fullmatch(repeat)
    if match is None:
        raise ValueError(f"repeat {repeat!r}: use <n>d, <n>w, <n>m or <n>y")
    n, unit = int(match[1]), match[2]
    if unit in "dw":
        return day + dt.timedelta(days=n * (7 if unit == "w" else 1))
    months = day.month - 1 + n * (12 if unit == "y" else 1)
    year, month = day.year + months // 12, months % 12 + 1
    last = (dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(year, month, min(day.day, last))


def file_next_occurrence(
    vault_root: Path, s: schema.Schema, closed: dict[str, Any], closed_stem: str
) -> dict[str, Any]:
    """File the next task of a recurring one (D124): same title and fields, `todo`, due one
    interval after the closed task's due date (or today), stepped past today when that is late."""
    today = dt.date.today()
    due = add_interval(schema.as_date(closed.get("due")) or today, closed["repeat"])
    while due <= today:
        due = add_interval(due, closed["repeat"])
    title = closed_stem.removeprefix(f"{closed.get('id')} ").strip() or closed_stem
    carried = {k: v for k, v in closed.items() if k not in NOT_CARRIED}
    order = list(s.fields_for("task"))
    with gitops.vault_lock(config.state_dir(vault_root), name="notes.lock"):
        values = {**carried, "id": next_task_id(vault_root), "status": "todo", "due": due}
        meta = {"type": "task", "created": today}
        meta |= {k: values[k] for k in order if k in values and k not in meta}
        meta |= {k: v for k, v in values.items() if k not in meta}
        source = s.types["task"].template(None)
        template = source.read_text(encoding="utf-8") if source else "## Log\n"
        body, _ = fill_section(template, "Log", f"- {today.isoformat()}: repeats [[{closed_stem}]]")
        target = write_new(vault_root, s, "task", title, meta, body, dt.datetime.now())
    return {"rel": vault.rel_path(vault_root, target), "id": meta["id"], "due": due.isoformat()}


def _new_home(
    vault_root: Path, s: schema.Schema, type_name: Any, target: Path, meta: dict[str, Any], changed: dict[str, Any]
) -> Path | None:
    """Where a note moves when `set` changed the field its folder depends on (`folder_by`), or None
    to stay. Archived notes stay archived; an occupied target refuses before anything is written."""
    note_type = s.types.get(type_name) if isinstance(type_name, str) else None
    if note_type is None or note_type.folder_by is None or note_type.folder_by.field not in changed:
        return None
    current = vault.rel_path(vault_root, target.parent)
    current = "" if current == "." else current
    wanted = note_type.folder_for(meta, target.stem)
    if current.startswith("Archive") or current == wanted:
        return None
    destination = vault_root / wanted / target.name
    if destination.exists():
        fail(3, "a note with that name already exists there", rel=vault.rel_path(vault_root, destination))
    return destination


def cmd_fill(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    target = (vault_root / args.file).resolve()
    if not vault.is_editable_note(vault_root, target) or not target.is_file():
        fail(2, f"{args.file} is not a note synapsidian may change")
    if vault.rel_path(vault_root, target).startswith("Sources/"):
        fail(2, "a source's body is never edited (D75)")
    content = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
    if not content.strip():
        fail(2, "the text is empty")
    if problems := secret_problems(content):
        fail(2, "the text looks like it holds a credential; nothing written", problems=problems)
    text = frontmatter.normalize_newlines(target.read_text(encoding="utf-8"))
    parsed = frontmatter.parse(text)
    if parsed.meta is None:
        fail(2, parsed.error or "note has no frontmatter")
    # The whole text, not parse().body: the frontmatter stays byte for byte (no YAML re-dump).
    updated, status = fill_section(text, args.section, content, args.before)
    if status != "kept":
        target.write_text(updated, encoding="utf-8")
    return {"ok": True, "rel": vault.rel_path(vault_root, target), "section": args.section, "status": status}


def template_section(s: schema.Schema, type_name: str, kind: str | None, title: str) -> str:
    """The body of `## title` in a type's template, so a note made before the template gained the
    section can get it through `fill` (D133). The template stays the only copy of the text."""
    if type_name not in s.types:
        fail(2, f"unknown type {type_name!r}", known=sorted(s.types))
    source = s.types[type_name].template(kind)
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True) if source else []
    found = next((sec for sec in sections(lines) if sec[0].casefold() == title.strip().casefold()), None)
    if found is None:
        fail(2, f"the {type_name} template has no section {title!r}")
    return "".join(lines[found[1] + 1 : found[2]]).strip("\n") + "\n"


def cmd_archive(args: argparse.Namespace, vault_root: Path) -> dict[str, Any]:
    """Move a note under Archive/, keeping its folder path. Never deletes, never overwrites."""
    source = (vault_root / args.file).resolve()
    if not vault.is_editable_note(vault_root, source) or not source.is_file():
        fail(2, f"{args.file} is not a note synapsidian may change")
    rel = vault.rel_path(vault_root, source)
    if rel.startswith("Archive/"):
        fail(2, f"{rel} is already archived")
    target = vault_root / "Archive" / rel
    if target.exists():
        fail(3, "an archived note with that path already exists", rel=vault.rel_path(vault_root, target))
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return {"ok": True, "from": rel, "to": vault.rel_path(vault_root, target)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault", help="vault path (default: plugin config)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    new = sub.add_parser("new")
    new.add_argument("--type", required=True)
    new.add_argument("--title", required=True)
    new.add_argument("--field", action="append", default=[], metavar="KEY=VALUE")
    new.add_argument("--body-file", help="use this file ('-' for stdin) as the body instead of the type template")

    daily = sub.add_parser("daily")
    daily.add_argument("--date")

    setp = sub.add_parser("set")
    setp.add_argument("--file", required=True, help="vault-relative path")
    setp.add_argument("--field", action="append", default=[], metavar="KEY=VALUE", required=True)

    sub.add_parser("next-id")

    sub.add_parser("where", help="print the vault path synapsidian resolves and its untracked state folder")

    archive = sub.add_parser("archive")
    archive.add_argument("--file", required=True, help="vault-relative path")

    fill = sub.add_parser("fill", help="write a section only when it is empty or missing")
    fill.add_argument("--file", required=True, help="vault-relative path")
    fill.add_argument("--section", required=True, metavar="TITLE", help="the `## TITLE` section to fill")
    fill.add_argument("--before", metavar="TITLE", help="where a missing section goes (default: the end)")
    fill.add_argument("--body-file", default="-", help="file with the text, or - for stdin (default)")

    section = sub.add_parser("section", help="print one `## ` section of a type's body template (for fill)")
    section.add_argument("--type", required=True)
    section.add_argument("--kind", help="the kind whose own template to read, when it has one")
    section.add_argument("--section", required=True, metavar="TITLE")

    args = parser.parse_args()
    vault_root = config.write_vault(args.vault)
    if vault_root is None or not vault_root.is_dir():
        fail(2, "vault not found; run /synapsidian:setup", vault=str(vault_root))
    s = schema.load(vault_root)

    match args.cmd:
        case "new":
            result = cmd_new(args, vault_root, s)
        case "daily":
            result = cmd_daily(args, vault_root, s)
        case "set":
            result = cmd_set(args, vault_root, s)
        case "next-id":
            result = {"ok": True, "id": next_task_id(vault_root)}
        case "archive":
            result = cmd_archive(args, vault_root)
        case "fill":
            result = cmd_fill(args, vault_root)
        case "section":
            sys.stdout.write(template_section(s, args.type, args.kind, args.section))
            return
        case "where":
            result = {
                "ok": True,
                "vault": str(vault_root),
                # Per-clone runtime state, never tracked: add-ons keep device-only data there (D140).
                "state": str(config.state_dir(vault_root)),
                "extensions": list(s.extensions),
                "timezone": (
                    vault.read_note(vault_root, vault_root / "About.md").get("timezone")
                    if (vault_root / "About.md").is_file()
                    else None
                ),
            }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
