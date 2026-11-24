"""Templater templates generated from the vault's schema, so notes made by hand in Obsidian
come out as synapsidian would write them (D110).

Every type a person may create (`obsidian_template` not false) gets `Templates/Generated/<Type>.md`,
and every `kind` with a body template of its own gets `Templates/Generated/<Type> - <Kind>.md`.
A template asks for the title and what the schema needs, numbers ids (`sequence` fields),
writes the frontmatter, adds the type's body template, and moves the note to the folder and
file name `synapsidian note new` would give it. The daily note template stays on the core syntax
(`{{date}}`): Obsidian's Daily notes fills it, not Templater.

The files belong to synapsidian: `sync` rewrites one only while it still holds what synapsidian wrote
last (a hash in `.synapsidian/generated-templates.json`), so a template the user edited is kept and
reported, never overwritten. The folder was `Templates/Synapsidian/` before D119: `sync` removes the
unedited files there like any template synapsidian no longer ships.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import Field, NoteType, Schema

FOLDER = "Templates/Generated"
LEGACY_FOLDERS = ("Templates/Synapsidian",)  # where earlier versions generated them (D119)
DAILY = "Templates/Daily.md"
RECORD = Path(".synapsidian") / "generated-templates.json"
RUNTIME = Path(__file__).with_name("templater.js")
CURSOR = "<% tp.file.cursor() %>"
SKIPPED = {"tags", "aliases"}  # optional lists a person adds by hand


@dataclass(slots=True)
class Synced:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # edited by the user: synapsidian's newer version not written


def daily(s: Schema) -> str:
    source = s.types["daily"].template()
    body = source.read_text(encoding="utf-8") if source else ""
    return "---\ntype: daily\ncreated: {{date:YYYY-MM-DD}}\ndate: {{date:YYYY-MM-DD}}\n---\n" + body


def wanted(s: Schema) -> dict[str, str]:
    """Vault-relative path -> content of every template synapsidian manages in this vault."""
    files = {DAILY: daily(s)} if "daily" in s.types else {}
    runtime = RUNTIME.read_text(encoding="utf-8")
    for note_type in s.types.values():
        if not note_type.obsidian_template:
            continue
        for kind, choices in variants(s, note_type):
            label = note_type.name.capitalize() + (f" - {kind.capitalize()}" if kind else "")
            files[f"{FOLDER}/{label}.md"] = render(s, note_type, label, kind, choices, runtime)
    return files


def hotkeys(s: Schema) -> list[str]:
    """Templater entries for the generated templates: a plain path gives it an Insert and a
    Create command in the command palette, so each type can get a hotkey."""
    return sorted(path for path in wanted(s) if path.startswith(f"{FOLDER}/"))


def variants(s: Schema, note_type: NoteType) -> list[tuple[str | None, list[str]]]:
    """(kind fixed by this template, kinds to choose from) per template of the type.

    A kind with a body template of its own gets its own template; the type's plain template
    offers the other kinds, and is left out when a required kind has none left.
    """
    kind = s.fields_for(note_type.name).get("kind")
    if kind is None or not kind.enum:
        return [(None, [])]
    own = [k for k in kind.enum if _has_own_template(note_type, k)]
    rest = [k for k in kind.enum if k not in own]
    found: list[tuple[str | None, list[str]]] = [(k, []) for k in own]
    if rest or not kind.required:
        found.insert(0, (None, rest))
    return found


def _has_own_template(note_type: NoteType, kind: str) -> bool:
    return any((d / f"{note_type.name}-{kind}.md").is_file() for d in note_type.template_dirs)


def render(s: Schema, note_type: NoteType, label: str, kind: str | None, choices: list[str], runtime: str) -> str:
    fields = s.fields_for(note_type.name)
    plan: list[dict[str, Any]] = []
    literals: dict[str, Any] = {}
    # `type` and the other fixed values are Templater output too: a template file with a literal
    # `type: task` would show up on the vault's Bases, which select notes by type (D102).
    lines = ["type: <% spec.type %>"]
    for name, f in fields.items():
        if name == "type" or name in SKIPPED:
            continue
        how = _how(s, note_type, f, kind, choices)
        if how["how"] == "literal":
            literals[name] = how["value"]
            lines.append(f"{name}: <% v.{name} %>")
        elif how["how"] == "empty":
            lines.append(f"{name}: []" if f.kind in ("links", "list") else f"{name}:")
        else:
            plan.append({"name": name, "kind": f.kind, **how})
            lines.append(f"{name}: <% v.{name} %>")
    spec = {
        "label": label,
        "type": note_type.name,
        "filename": note_type.filename,
        "folder": note_type.folder,
        "folder_by": {"field": note_type.folder_by.field, "folder": note_type.folder_by.folder}
        if note_type.folder_by
        else None,
        "literals": literals,
        "fields": plan,
    }
    # `%>` would end the Templater command early.
    spec_js = json.dumps(spec, ensure_ascii=False).replace("%>", "%\\u003e")
    head = (
        "<%*\n"
        f"// Generated by synapsidian from its schema: `synapsidian setup apply` rewrites this file while it is\n"
        f"// unchanged. To make your own variant, copy it out of {FOLDER}/ first.\n"
        f"const spec = {spec_js};\n"
        f"{runtime.rstrip()}\n"
        "-%>\n"
    )
    return head + "---\n" + "\n".join(lines) + "\n---\n" + _body(note_type, kind)


def _how(s: Schema, note_type: NoteType, f: Field, kind: str | None, choices: list[str]) -> dict[str, Any]:
    """How the template fills one field: a literal, a prompt, a choice, a number, or empty."""
    if f.name == "kind" and f.enum:
        if kind:
            return {"how": "literal", "value": kind}
        if not choices:  # every kind has a template of its own: the plain one is the no-kind note
            return {"how": "empty"}
        if len(choices) == 1 and f.required:
            return {"how": "literal", "value": choices[0]}
        return {"how": "choice", "options": choices, "optional": not f.required}
    if f.sequence:
        seq = f.sequence
        return {"how": "sequence", "prefix": seq.prefix, "legacy": list(seq.legacy), "per": seq.per}
    if f.name == "created":
        return {"how": "today"}
    by_field = note_type.folder_by.field if note_type.folder_by else None
    if f.kind == "link" and (f.required or f.name == by_field):
        if f.name in s.types:  # `project` links a project hub: offer the existing ones
            return {"how": "note", "type": f.name, "optional": not f.required}
        return {"how": "link"} if f.required else {"how": "empty"}
    if not f.required:
        return {"how": "empty"}
    if f.enum:
        options = [str(f.default), *(e for e in f.enum if e != str(f.default))] if f.default else list(f.enum)
        return {"how": "choice", "options": options, "optional": False}
    if f.default is not None:
        return {"how": "literal", "value": f.default}
    match f.kind:
        case "date":
            return {"how": "date"}
        case "number":
            return {"how": "number"}
        case "text":
            return {"how": "text", "label": "Summary (one sentence)" if f.name == "summary" else f.name}
    return {"how": "empty"}


def _body(note_type: NoteType, kind: str | None) -> str:
    """The body template, with Templater's cursor in the first empty section."""
    source = note_type.template(kind)
    body = source.read_text(encoding="utf-8") if source else ""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
        if all(not x.strip() for x in lines[i + 1 : end]):
            lines.insert(i + 1, CURSOR)
            return "\n".join(lines) + "\n"
    return f"{body.rstrip(chr(10))}\n{CURSOR}\n" if body.strip() else f"{CURSOR}\n"


# --- writing ------------------------------------------------------------------------


def legacy(rel: str) -> bool:
    """A path in a folder earlier versions generated templates into."""
    return any(rel.startswith(f"{folder}/") for folder in LEGACY_FOLDERS)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def sync(vault_root: Path, s: Schema) -> Synced:
    """Write the wanted templates: new ones, and changed ones the user hasn't edited since synapsidian
    wrote them. A file synapsidian wrote for a type that is gone is removed the same way. The record
    of what synapsidian wrote is updated, and listed under `updated`/`created` when it changes."""
    result = Synced()
    record_path = vault_root / RECORD
    try:
        record: dict[str, str] = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    before = dict(record)
    files = wanted(s)
    for rel, text in files.items():
        path = vault_root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            result.created.append(rel)
        else:
            current = path.read_text(encoding="utf-8")
            if current == text:
                pass
            elif record.get(rel) == digest(current):
                path.write_text(text, encoding="utf-8")
                result.updated.append(rel)
            else:
                result.kept.append(f"{rel}: edited, so synapsidian's newer version was not written")
                continue
        record[rel] = digest(text)
    for rel in sorted(set(record) - set(files)):
        path = vault_root / rel
        if path.is_file() and digest(path.read_text(encoding="utf-8")) == record[rel]:
            path.unlink()
            result.removed.append(rel)
        elif path.is_file() and legacy(rel):
            result.kept.append(f"{rel}: edited, so it stays, but Templater now lists only {FOLDER}/")
        elif path.is_file():
            result.kept.append(f"{rel}: edited, so it stays although synapsidian no longer ships it")
        del record[rel]
    for folder in LEGACY_FOLDERS:
        old = vault_root / folder
        if old.is_dir() and not any(p.name != ".DS_Store" for p in old.iterdir()):
            for leftover in old.iterdir():
                leftover.unlink()
            old.rmdir()
    if record != before:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        existed = record_path.exists()
        record_path.write_text(json.dumps(dict(sorted(record.items())), indent=2) + "\n", encoding="utf-8")
        (result.updated if existed else result.created).append(RECORD.as_posix())
    return result
