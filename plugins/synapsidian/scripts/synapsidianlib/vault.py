"""Walk the vault's markdown notes. One scanner, one exclusion list, for every script."""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import frontmatter
from .config import true_case

# Never notes: app state, git, trash, plugin-internal folders.
SKIP_DIRS = frozenset({".obsidian", ".git", ".trash", ".claude", "Attachments", "Bases", "Templates"})
# Notes, but left out of search and the brief unless asked for.
COLD_DIRS = frozenset({"Archive", "Sources"})
# Markdown that belongs to a plugin, not to synapsidian: Excalidraw drawings carry their scene in a .md file.
NOT_NOTE_SUFFIXES = (".excalidraw.md",)


@dataclass(slots=True)
class Note:
    path: Path
    rel: str  # vault-relative, forward slashes, NFC
    meta: dict[str, Any] | None
    body: str
    error: str | None
    mtime: float

    @property
    def title(self) -> str:
        return Path(self.rel).stem

    @property
    def folder(self) -> str:
        parent = Path(self.rel).parent.as_posix()
        return "" if parent == "." else parent

    @property
    def type(self) -> str | None:
        return (self.meta or {}).get("type")

    def get(self, key: str, default: Any = None) -> Any:
        return (self.meta or {}).get(key, default)


def rel_path(vault: Path, path: Path) -> str:
    try:
        rel = path.relative_to(vault)
    except ValueError:
        rel = true_case(path).relative_to(true_case(vault))
    return unicodedata.normalize("NFC", rel.as_posix())


def read_note(vault: Path, path: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed = frontmatter.parse(text)
    return Note(path, rel_path(vault, path), parsed.meta, parsed.body, parsed.error, path.stat().st_mtime)


def iter_notes(vault: Path, *, include_cold: bool = False) -> Iterator[Note]:
    skip = SKIP_DIRS if include_cold else SKIP_DIRS | COLD_DIRS
    for root, dirs, files in os.walk(vault):
        root_path = Path(root)
        at_top = root_path == vault
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (at_top and d in skip) and d not in SKIP_DIRS)
        for name in sorted(files):
            if name.endswith(".md") and not name.startswith("._") and not name.endswith(NOT_NOTE_SUFFIXES):
                yield read_note(vault, root_path / name)


def find_by_stem(vault: Path, stem: str) -> Path | None:
    """A note (archived ones included) whose file name is `stem`, ignoring letter case as
    Obsidian's link resolution does, or None."""
    key = unicodedata.normalize("NFC", stem).casefold() + ".md"
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS)
        for name in files:
            if unicodedata.normalize("NFC", name).casefold() == key:
                return Path(root) / name
    return None


def is_inside(vault: Path, path: Path) -> bool:
    """True when `path` is the vault or inside it, letter case as on disk (macOS)."""
    return true_case(path).is_relative_to(true_case(vault))


# Read as instructions by Claude Code in that folder, wherever they sit.
INSTRUCTION_FILES = frozenset({"claude.md", "claude.local.md", "agents.md"})


def is_editable_note(vault: Path, path: Path, *, about: bool = False) -> bool:
    """A `.md` note inside the vault that synapsidian's scripts may change: not in app, plugin or
    template folders (Templater runs a template's code), not under a dot-folder, not an
    instructions file, and About.md only when `about` (its Rules and `protected` reach every
    session, D120; `note set` may change its other fields)."""
    if path.suffix != ".md" or not is_inside(vault, path):
        return False
    parts = Path(rel_path(vault, path)).parts
    if not parts or parts[0] in SKIP_DIRS or any(p.startswith(".") for p in parts):
        return False
    return parts[-1].casefold() not in INSTRUCTION_FILES and (about or parts != ("About.md",))
