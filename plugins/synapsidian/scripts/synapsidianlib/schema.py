"""Note types from schema/types.yaml: validation, value coercion and file naming.

A vault can carry extensions (D90): `<vault>/.synapsidian/extensions/<name>/schema.yaml`, written
by `synapsidian setup extension` from an add-on plugin such as synapsidian-work. An extension adds
types (`types:`) and widens existing ones (`extend: <type>:`): `fields:` adds a field or
gives an existing one more `enum` values, `folder_by:` gives a type that has none a
folder that depends on one of its fields (D102), and `sections:` (only on `about`) adds a body
section or, with `subsection:`, a `###` inside an existing one (D160). Every extension's types are merged before
any `extend:`, and an `extend:` of a type nothing defines is skipped with a warning (D106).
A type's own `folder` may hold `{title}`, giving each note a folder of its own (a project
hub in `Projects/<title>/`). Its `templates/` win over the
core templates. The files live in the vault, so every process that knows the vault (hooks
included) sees the same schema, whether or not the add-on plugin is installed there.

An extension's `extension.yaml` may say `requires: synapsidian >= X.Y.Z`, the oldest core that
reads its schema. A vault synced between machines can hold an extension installed by a newer
core than this one: `load` then raises a `SchemaError` that says to update synapsidian, before
the merge fails on a key this core doesn't know (D161). Every load failure is a `SchemaError`.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from .config import SCHEMA_DIR, core_version

EXTENSIONS_DIR = Path(".synapsidian") / "extensions"
REQUIRES_RE = re.compile(r"synapsidian\s*>=\s*(\d+(?:\.\d+){0,2})")


class SchemaError(ValueError):
    """The vault's schema did not load: a broken extension, or one written for a newer core (D161)."""


LINK_RE = re.compile(r"\[\[[^\[\]\n]+\]\]")
URL_RE = re.compile(r"https?://\S+$")
ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')


@dataclass(frozen=True, slots=True)
class Field:
    name: str
    required: bool = False
    kind: str = "text"
    enum: tuple[str, ...] = ()
    pattern: re.Pattern[str] | None = None
    default: Any = None
    # A number one above the highest this field holds among the type's notes (D110):
    # `{prefix: T, legacy: [ZAD-]}` for task ids, `{per: project}` for a number within a project.
    sequence: Sequence | None = None
    # The plugin that declared the field: `synapsidian` for the core, else the extension's name.
    owner: str = "synapsidian"


@dataclass(frozen=True, slots=True)
class Section:
    """A body section of the `about` note (D160): the interview asks `ask` while it is empty.

    `subsection` set means a `### subsection` inside the existing `## title` section."""

    title: str
    ask: str
    owner: str = "synapsidian"
    subsection: str | None = None


@dataclass(frozen=True, slots=True)
class Sequence:
    prefix: str = ""
    legacy: tuple[str, ...] = ()
    per: str | None = None


@dataclass(frozen=True, slots=True)
class FolderBy:
    """A type's folder when one of its fields is set: `folder` is a format string over `field`."""

    field: str
    folder: str


@dataclass(frozen=True, slots=True)
class NoteType:
    name: str
    folder: str
    filename: str
    summary_required: bool
    fields: dict[str, Field] = field(default_factory=dict)
    template_dirs: tuple[Path, ...] = (SCHEMA_DIR / "templates",)
    folder_by: FolderBy | None = None
    # False for a type only scripts or Claude write: it gets no Obsidian template (D110).
    obsidian_template: bool = True
    # Only the `about` type has them: the body sections the interview fills (D160).
    sections: tuple[Section, ...] = ()

    def template(self, kind: object = None) -> Path | None:
        """Body template: `<type>-<kind>.md` wins over `<type>.md`; extension dirs win over the core's."""
        names = ([f"{self.name}-{kind}.md"] if kind else []) + [f"{self.name}.md"]
        return next((d / n for n in names for d in self.template_dirs if (d / n).is_file()), None)

    @property
    def folder_prefix(self) -> str:
        """The fixed part of `folder`: all of it, or what comes before `{title}` (`Projects`)."""
        return self.folder.split("{", 1)[0].rstrip("/")

    def own_folder(self, title: str) -> str:
        """The type's folder for a note of this title: `folder`, with `{title}` filled in."""
        return self.folder.replace("{title}", clean_title(title)) if "{title}" in self.folder else self.folder

    def folder_for(self, meta: dict[str, Any], title: str = "") -> str:
        """Where a note with this frontmatter and title belongs: the `folder_by` folder when its
        field names a note, else the type's own folder."""
        value = link_target(meta.get(self.folder_by.field)) if self.folder_by else ""
        if not value:
            return self.own_folder(title)
        return self.folder_by.folder.format_map({self.folder_by.field: value})

    def legacy_folders(self, title: str) -> set[str]:
        """Folders a note of this type may still sit in although `folder_for` points elsewhere:
        the type's own folder (notes written before a `folder_by` applied) and the fixed part of
        a `{title}` folder (notes written before it had one). `setup apply` refiles from these."""
        return {self.own_folder(title), self.folder_prefix}

    def folder_problem(self, folder: str, meta: dict[str, Any], title: str = "") -> str | None:
        """Why a note of this type can't sit in `folder`, or None; Archive/ is never checked."""
        expected = self.folder_for(meta, title)
        if folder == expected or folder in self.legacy_folders(title) or folder.startswith("Archive"):
            return None
        where = f"{expected or 'the vault root'}/"
        if (own := self.own_folder(title)) != expected:
            where += f" (or {own or 'the vault root'}/)"
        return f"type {self.name} belongs in {where}, found in {folder or 'the vault root'}/"


@dataclass(frozen=True, slots=True)
class Schema:
    universal: dict[str, Field]
    types: dict[str, NoteType]
    extensions: tuple[str, ...] = ()
    # What an extension asked for that no installed schema could give it (an `extend:` of a type
    # nobody defines): skipped and reported by `setup check`, never fatal (D106).
    warnings: tuple[str, ...] = ()

    def fields_for(self, type_name: str) -> dict[str, Field]:
        note_type = self.types[type_name]
        merged = dict(self.universal)
        if not note_type.summary_required:
            merged["summary"] = Field("summary", required=False, kind="text")
        merged.update(note_type.fields)
        return merged


def _field(name: str, spec: dict[str, Any]) -> Field:
    pattern = spec.get("pattern")
    seq = spec.get("sequence")
    return Field(
        name=name,
        required=bool(spec.get("required", False)),
        kind=spec.get("kind", "text"),
        enum=tuple(str(v) for v in spec.get("enum", ())),
        pattern=re.compile(pattern) if pattern else None,
        default=spec.get("default"),
        owner=str(spec.get("owner") or "synapsidian"),
        sequence=Sequence(
            prefix=str(seq.get("prefix") or ""),
            legacy=tuple(str(p) for p in seq.get("legacy") or ()),
            per=seq.get("per"),
        )
        if isinstance(seq, dict)
        else None,
    )


def extension_dirs(vault_root: Path | None) -> list[Path]:
    """The vault's installed extensions, in name order."""
    root = vault_root / EXTENSIONS_DIR if vault_root else None
    if root is None or not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if (p / "schema.yaml").is_file())


def load(vault_root: Path | None = None) -> Schema:
    """The core schema plus the extensions installed in `vault_root` (none without a vault).

    Raises `SchemaError` (a `ValueError`) when it can't load, with a message a person can act on."""
    try:
        files = tuple(
            (d / "schema.yaml", (d / "schema.yaml").stat().st_mtime_ns, _mtime(d / "extension.yaml"))
            for d in extension_dirs(vault_root)
        )
        return _load(files)
    except SchemaError:
        raise
    except (ValueError, yaml.YAMLError, OSError) as exc:
        raise SchemaError(str(exc)) from exc


def _mtime(path: Path) -> int:
    return path.stat().st_mtime_ns if path.is_file() else -1


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def requires_problem(manifest: dict[str, Any], name: str, core: str | None) -> str | None:
    """Why this core (version `core`) can't read the extension `manifest` describes, or None (D161).

    No `requires`, or a core whose version can't be read, is no problem: the merge still checks."""
    requires = manifest.get("requires")
    if requires is None:
        return None
    match = REQUIRES_RE.fullmatch(str(requires).strip())
    if not match:
        return f"extension {name}: requires {requires!r} must read `synapsidian >= X.Y.Z`"
    needed = match.group(1)
    if core is None or version_tuple(core) >= version_tuple(needed):
        return None
    version = f" {manifest['version']}" if manifest.get("version") else ""
    return f"extension {name}{version} needs synapsidian >= {needed}, this is {core}; update the synapsidian plugin"


def _manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return data if isinstance(data, dict) else {}


def merge_extension(raw: dict[str, Any], ext: dict[str, Any], name: str) -> list[str]:
    """Fold one extension's schema into the raw core schema, in place; returns its warnings."""
    return merge_extensions(raw, [(name, ext)])


def merge_extensions(raw: dict[str, Any], exts: list[tuple[str, dict[str, Any]]]) -> list[str]:
    """Fold several extensions into the raw core schema, in place: every `types:` first, then
    every `extend:`, so one add-on may widen a type another defines whatever their names.

    A conflict with the core (a core type redefined, a field redefined, a second `folder_by`)
    raises. A type two extensions both define keeps the first one's (in name order) and warns:
    a type moving from one add-on to another (D109) is defined by both until the old one is
    updated. An `extend:` of a type nothing defines is skipped with a warning: an add-on that
    widens another add-on's type keeps working where that one isn't installed, and an extension
    written for an older core never stops the vault's schema from loading (D106)."""
    core = set(raw["types"])
    defined_by: dict[str, str] = {}
    warnings: list[str] = []
    for name, ext in exts:
        for type_name, spec in (ext.get("types") or {}).items():
            if type_name in core:
                raise ValueError(f"extension {name}: type {type_name!r} already exists; widen it under `extend:`")
            if type_name in defined_by:
                warnings.append(
                    f"extension {name}: type {type_name!r} is also defined by {defined_by[type_name]}, "
                    f"whose definition is used; skipped"
                )
                continue
            defined_by[type_name] = name
            raw["types"][type_name] = spec
    for name, ext in exts:
        warnings += _extend(raw, ext, name)
    return warnings


def _extend(raw: dict[str, Any], ext: dict[str, Any], name: str) -> list[str]:
    warnings: list[str] = []
    for type_name, spec in (ext.get("extend") or {}).items():
        if type_name not in raw["types"]:
            warnings.append(f"extension {name}: extends type {type_name!r}, which no installed schema defines; skipped")
            continue
        unknown = set(spec) - {"fields", "folder_by", "sections"}
        if unknown:
            raise ValueError(f"extension {name}: extend: {type_name} can't set {', '.join(sorted(unknown))}")
        fields = raw["types"][type_name].setdefault("fields", {})
        for fname, fspec in (spec.get("fields") or {}).items():
            if fname not in fields:
                fields[fname] = {**fspec, "owner": name}
            elif set(fspec) - {"enum"} or not fields[fname].get("enum"):
                raise ValueError(f"extension {name}: {type_name}.{fname} exists; only its enum can be widened")
            else:
                fields[fname]["enum"] = [
                    *fields[fname]["enum"],
                    *(v for v in fspec["enum"] if v not in fields[fname]["enum"]),
                ]
        if "sections" in spec:
            if type_name != "about":
                raise ValueError(f"extension {name}: extend: {type_name} can't set sections; only about has them")
            sections = raw["types"][type_name].setdefault("sections", [])
            for entry in spec["sections"] or ():
                if warning := _add_section(sections, entry, name):
                    warnings.append(warning)
        # After the fields, so one `extend:` block can add a field and file notes by it.
        if "folder_by" in spec:
            if raw["types"][type_name].get("folder_by"):
                raise ValueError(f"extension {name}: {type_name} already has a folder_by")
            raw["types"][type_name]["folder_by"] = spec["folder_by"]
    return warnings


def _add_section(sections: list[dict[str, Any]], entry: dict[str, Any], name: str) -> str | None:
    """Add one `about` section from an extension to the raw list, in place; a warning when it is skipped.

    A new `title` adds a `## title` section. A `title` that exists needs `subsection:`, which adds a
    `### subsection` inside it; a parent no installed schema defines is skipped (D106)."""
    title, ask, sub = (str(entry.get(k) or "").strip() for k in ("title", "ask", "subsection"))
    if not title or not ask:
        raise ValueError(f"extension {name}: an about section needs a title and an ask")
    top = {s["title"].casefold() for s in sections if not s.get("subsection")}
    if sub:
        if title.casefold() not in top:
            return f"extension {name}: about section {title!r} to add {sub!r} to isn't defined; skipped"
        if any(
            s["title"].casefold() == title.casefold() and (s.get("subsection") or "").casefold() == sub.casefold()
            for s in sections
        ):
            raise ValueError(f"extension {name}: about section {title!r} already has a subsection {sub!r}")
    elif title.casefold() in top:
        raise ValueError(f"extension {name}: about section {title!r} exists; add a `subsection:` to extend it")
    sections.append({"title": title, "ask": ask, "owner": name, **({"subsection": sub} if sub else {})})
    return None


def _folder(type_name: str, spec: dict[str, Any]) -> str:
    folder = str(spec["folder"]).strip("/")
    if re.search(r"\{(?!title\})", folder):
        raise ValueError(f"{type_name}.folder: the only placeholder a folder may hold is {{title}}, got {folder!r}")
    return folder


def _folder_by(type_name: str, spec: dict[str, Any], fields: dict[str, Field], warnings: list[str]) -> FolderBy | None:
    raw = spec.get("folder_by")
    if not raw:
        return None
    by = FolderBy(field=str(raw.get("field", "")), folder=str(raw.get("folder", "")).strip("/"))
    if by.field not in fields:
        # The field comes from a schema that isn't there: an extension written for an older core
        # (synapsidian-projects 0.1 filed tasks by the core's own `project` field). Skipped like an
        # `extend:` of a missing type, so the vault's schema still loads (D106).
        warnings.append(f"{type_name}.folder_by: no field {by.field!r} to file by; skipped")
        return None
    if fields[by.field].kind != "link":
        raise ValueError(f"{type_name}.folder_by: {by.field!r} is not a link field of {type_name}")
    if "{" + by.field + "}" not in by.folder or re.search(r"\{(?!" + re.escape(by.field) + r"\})", by.folder):
        raise ValueError(f"{type_name}.folder_by: folder must use exactly {{{by.field}}}, got {by.folder!r}")
    return by


@cache
def _load(extensions: tuple[tuple[Path, int, int], ...]) -> Schema:
    raw = yaml.safe_load((SCHEMA_DIR / "types.yaml").read_text(encoding="utf-8"))
    template_dirs = [SCHEMA_DIR / "templates"]
    # Before anything of the extension is read: a key this core doesn't know would fail the merge
    # with a message that doesn't say the fix is a newer synapsidian (D161).
    core = core_version()
    for path, *_ in extensions:
        if problem := requires_problem(_manifest(path.parent / "extension.yaml"), path.parent.name, core):
            raise SchemaError(problem)
    loaded = [(path.parent.name, yaml.safe_load(path.read_text(encoding="utf-8")) or {}) for path, *_ in extensions]
    warnings = merge_extensions(raw, loaded)
    for path, *_ in extensions:
        template_dirs.insert(0, path.parent / "templates")
    universal = {name: _field(name, spec) for name, spec in raw["universal"].items()}
    types = {}
    for name, spec in raw["types"].items():
        fields = {fname: _field(fname, fspec) for fname, fspec in spec.get("fields", {}).items()}
        types[name] = NoteType(
            name=name,
            folder=_folder(name, spec),
            filename=spec["filename"],
            summary_required=spec.get("summary", True),
            fields=fields,
            template_dirs=tuple(template_dirs),
            folder_by=_folder_by(name, spec, fields, warnings),
            obsidian_template=bool(spec.get("obsidian_template", True)),
            sections=tuple(
                Section(
                    title=str(sec["title"]),
                    ask=str(sec["ask"]),
                    owner=str(sec.get("owner") or "synapsidian"),
                    subsection=str(sec["subsection"]) if sec.get("subsection") else None,
                )
                for sec in spec.get("sections") or ()
            ),
        )
    return Schema(universal, types, tuple(path.parent.name for path, *_ in extensions), tuple(warnings))


# --- values -----------------------------------------------------------------


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def link_target(value: Any) -> str:
    """'[[Note|alias]]' or '[[Note#Heading]]' -> 'Note', made safe as a folder name; '' for
    anything that isn't a wikilink (empty, a URL, a list)."""
    if not isinstance(value, str) or not LINK_RE.fullmatch(value.strip()):
        return ""
    target = value.strip()[2:-2].split("|", 1)[0].split("#", 1)[0]
    return clean_title(target.rsplit("/", 1)[-1])


def as_link(value: str) -> str:
    """'Foo' -> '[[Foo]]'; an existing wikilink or a web URL (an email thread, a PR) is kept."""
    value = value.strip()
    return value if LINK_RE.fullmatch(value) or URL_RE.match(value) else f"[[{value}]]"


def coerce(f: Field, value: Any) -> Any:
    """Turn a CLI string into the typed YAML value the schema expects."""
    if value is None:
        return None
    match f.kind:
        case "date":
            parsed = as_date(value)
            if parsed is None:
                raise ValueError(f"{f.name}: '{value}' is not a YYYY-MM-DD date")
            return parsed
        case "link":
            return as_link(str(value))
        case "links":
            # `[[A]], [[B, with a comma]],https://x`: each wikilink whole, commas inside kept; the rest split on
            # commas. Whitespace before an item is skipped first, or `[^,]+` would start at the space after a
            # comma and cut the next wikilink at its first inner comma.
            items = value if isinstance(value, list) else re.findall(rf"\s*({LINK_RE.pattern}|[^,]+)", str(value))
            return [as_link(str(v)) for v in items if str(v).strip()]
        case "list":
            items = value if isinstance(value, list) else [v.strip() for v in str(value).split(",") if v.strip()]
            return items
        case "number":
            return float(value) if "." in str(value) else int(value)
        case _:
            return str(value)


# --- validation ---------------------------------------------------------------


def check(f: Field, value: Any) -> str | None:
    """Why `value` isn't valid for field `f`, or None when it is."""
    match f.kind:
        case "date":
            if as_date(value) is None:
                return f"`{f.name}` should be a YYYY-MM-DD date, got {value!r}"
        case "link":
            if not (isinstance(value, str) and (LINK_RE.fullmatch(value.strip()) or URL_RE.match(value.strip()))):
                return f'`{f.name}` should be a quoted wikilink like "[[Note]]" or a URL, got {value!r}'
        case "links":
            if not isinstance(value, list) or not all(
                isinstance(v, str) and (LINK_RE.fullmatch(v.strip()) or URL_RE.match(v.strip())) for v in value
            ):
                return f"`{f.name}` should be a list of quoted wikilinks or URLs"
        case "list":
            if not isinstance(value, list):
                return f"`{f.name}` should be a list"
        case "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                return f"`{f.name}` should be a number"
        case _:
            if f.enum and str(value) not in f.enum:
                return f"`{f.name}` is {value!r}; allowed: {', '.join(f.enum)}"
            if f.pattern and not f.pattern.fullmatch(str(value)):
                return f"`{f.name}` is {value!r}; expected pattern {f.pattern.pattern}"
    return None


def validate(meta: dict[str, Any] | None, rel_path: str, schema: Schema | None = None) -> list[str]:
    """Problems with one note's frontmatter. `rel_path` is relative to the vault root."""
    schema = schema or load()
    if meta is None:
        return ["note has no frontmatter"]
    type_name = meta.get("type")
    if is_empty(type_name):
        return ["`type` is missing"]
    if type_name not in schema.types:
        return [f"unknown type {type_name!r}; known: {', '.join(sorted(schema.types))}"]

    note_type = schema.types[type_name]
    issues: list[str] = []
    for f in schema.fields_for(type_name).values():
        value = meta.get(f.name)
        if is_empty(value):
            if f.required:
                issues.append(f"`{f.name}` is required for type {type_name}")
            continue
        if problem := check(f, value):
            issues.append(problem)

    folder = str(Path(rel_path).parent).replace("\\", "/")
    folder = "" if folder == "." else folder
    if problem := note_type.folder_problem(folder, meta, Path(rel_path).stem):
        issues.append(problem)

    if problem := filename_problem(Path(rel_path).stem):
        issues.append(problem)
    return issues


# --- names --------------------------------------------------------------------


def filename_problem(stem: str) -> str | None:
    if not stem.strip():
        return "file name is empty"
    if ILLEGAL_FILENAME_CHARS.search(stem):
        return f"file name {stem!r} contains a character Obsidian links can't use"
    if stem != unicodedata.normalize("NFC", stem):
        return f"file name {stem!r} is not NFC-normalised"
    return None


def clean_title(title: str) -> str:
    title = unicodedata.normalize("NFC", title)
    title = ILLEGAL_FILENAME_CHARS.sub(" ", title)
    return re.sub(r"\s+", " ", title).strip(" .")


def filename_for(note_type: NoteType, meta: dict[str, Any], title: str, now: dt.datetime) -> str:
    """The file name from the type's pattern. `{date}` is the note's `date` field, else its
    `created` (a decision written down later is filed under the day it was made), else today."""
    values = {
        **{k: (v.isoformat() if isinstance(v, dt.date) else v) for k, v in meta.items()},
        "title": clean_title(title),
        "date": as_date(meta.get("date")) or as_date(meta.get("created")) or now.date(),
        "time": now.strftime("%H%M"),
    }
    values["date"] = values["date"].isoformat()
    name = note_type.filename.format_map(_Defaulting(values))
    return clean_title(name)


class _Defaulting(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return ""
