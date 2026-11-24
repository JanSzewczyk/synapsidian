"""[[Links]] in note text and what they resolve to. No dependencies: `commit.py` runs without PyYAML."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from . import gitops

LINK = re.compile(r"(?<!!)\[\[([^\[\]|#\n]+)((?:#[^\[\]|\n]*)?(?:\|[^\[\]\n]*)?)\]\]")
# Fenced blocks and inline code: Obsidian shows [[...]] there as text, not as a link.
CODE = re.compile(r"^(```|~~~).*?^\1|`[^`\n]+`", re.MULTILINE | re.DOTALL)
NON_NOTE_DIRS = {".git", ".obsidian", ".trash", ".synapsidian"}
# What `new_unresolved` leaves alone, as the health check does (`vault.iter_notes`; a test keeps
# the two in step): folders that hold no notes, at any depth, dot-folders, and Excalidraw
# drawings, all written by scripts; verbatim copies and archived notes, which are never edited.
NOT_NOTE_DIRS = {"Attachments", "Bases", "Templates"}
NOT_NOTE_SUFFIXES = (".excalidraw.md",)
NEVER_EDITED_TOP = {"Sources", "Archive"}


def outside_code(text: str) -> list[tuple[bool, str]]:
    """`text` split into (is_code, segment) pieces, in order."""
    pieces: list[tuple[bool, str]] = []
    last = 0
    for match in CODE.finditer(text):
        pieces += [(False, text[last : match.start()]), (True, match.group(0))]
        last = match.end()
    return [*pieces, (False, text[last:])]


def targets(text: str) -> list[str]:
    """Link targets in `text` outside code, in order. Given a whole file, frontmatter links count too."""
    return [m.group(1).strip() for code, part in outside_code(text) if not code for m in LINK.finditer(part)]


def linked_names(vault_root: Path) -> dict[str, list[str]]:
    """casefold(name) -> exact names, for every file Obsidian can link to (notes by stem, others by name)."""
    names: dict[str, list[str]] = defaultdict(list)
    for path in vault_root.rglob("*"):
        if not path.is_file() or NON_NOTE_DIRS & set(path.relative_to(vault_root).parts):
            continue
        name = unicodedata.normalize("NFC", path.stem if path.suffix == ".md" else path.name)
        names[name.casefold()].append(name)
        if path.suffix != ".md":
            names[unicodedata.normalize("NFC", path.stem).casefold()].append(path.stem)
    return names


def leaf(target: str) -> str:
    """The name a link resolves by: `Folder/Note` -> `note`."""
    return unicodedata.normalize("NFC", target.rsplit("/", 1)[-1]).casefold()


def new_unresolved(vault_root: Path, files: Iterable[str]) -> list[dict[str, str]]:
    """Links in `files` (vault-relative notes) that resolve to no file and that the last commit
    of the file didn't have: the ones this run wrote. A link that was already broken is the
    health run's to report, not something to hand back to every skill that touches the note."""
    listed = list(dict.fromkeys(files))

    def committed(rel: str) -> set[str] | None:
        """The link names in the file's last committed version, or None when it has none."""
        shown = gitops.git(vault_root, "show", f"HEAD:{rel}", check=False)
        return {leaf(t) for t in targets(shown.stdout)} if shown.returncode == 0 else None

    # A note `note set` moved is listed under both paths: what it linked at the old one isn't new.
    moved_from: set[str] = set()
    for rel in listed:
        if rel.endswith(".md") and not (vault_root / rel).exists():
            moved_from |= committed(rel) or set()

    added: list[tuple[str, str]] = []
    for rel in listed:
        path, parts = vault_root / rel, rel.split("/")
        if not rel.endswith(".md") or rel.endswith(NOT_NOTE_SUFFIXES) or not path.is_file():
            continue
        if parts[0] in NEVER_EDITED_TOP or any(p.startswith(".") or p in NOT_NOTE_DIRS for p in parts[:-1]):
            continue
        now = targets(path.read_text(encoding="utf-8", errors="replace"))
        if not now:
            continue
        had = committed(rel)
        had = moved_from if had is None else had
        added += [(rel, t) for t in dict.fromkeys(now) if leaf(t) not in had]
    if not added:
        return []
    names = linked_names(vault_root)
    return [{"rel": rel, "link": target} for rel, target in added if not names.get(leaf(target))]
