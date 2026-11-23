"""Task ids: `T<n>` (D93), and the one-time move from the older `ZAD-<n>`."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import blocks, vault

# Matched with fullmatch only: a bare `T12` is too short a token to find inside running text.
TASK_ID = re.compile(r"T([1-9][0-9]*)")
LEGACY_TASK_ID = re.compile(r"ZAD-([1-9][0-9]*)")  # synapsidian < 0.14
LEGACY_MENTION = re.compile(r"\bZAD-[1-9][0-9]*\b")
FRONTMATTER_ID = re.compile(r"""^(id:[ \t]*)(['"]?)ZAD-([1-9][0-9]*)\2[ \t]*$""", re.MULTILINE)
# Text files whose content can name a note: notes, Bases views, canvases.
LINKING_SUFFIXES = (".md", ".base", ".canvas")


def task_number(task_id: object) -> int | None:
    """n of `T<n>`, or of a legacy `ZAD-<n>` not migrated yet (so new ids never collide with it)."""
    text = str(task_id or "")
    match = TASK_ID.fullmatch(text) or LEGACY_TASK_ID.fullmatch(text)
    return int(match.group(1)) if match else None


@dataclass(slots=True)
class Migration:
    renamed: list[dict[str, str]] = field(default_factory=list)  # {from, to, old_rel, new_rel}
    relinked: list[str] = field(default_factory=list)  # files whose links or paths were rewritten
    skipped: list[dict[str, str]] = field(default_factory=list)  # {rel, reason}
    mentions_left: list[dict[str, object]] = field(default_factory=list)  # {rel, ids}: plain text, not touched

    @property
    def touched(self) -> list[str]:
        """Every vault-relative path to commit: old and new name of each renamed note, relinked files."""
        paths = [p for r in self.renamed for p in (r["old_rel"], r["new_rel"])] + self.relinked
        return list(dict.fromkeys(paths))


def migrate_legacy_ids(vault_root: Path) -> Migration:
    """Rename every `ZAD-n` task to `Tn`: its `id`, its file name, and each place that names the file.

    A reference is rewritten only as the note's full old name (`ZAD-5 Retire the Notion workflows`),
    which covers `[[links]]`, `[[link|alias]]`, embeds and paths in Bases and canvases. A bare `ZAD-5`
    in running text is left alone and reported: other tools (a Notion board) use the same ids.
    """
    result = Migration()
    taken = {
        int(match.group(1))
        for note in vault.iter_notes(vault_root, include_cold=True)
        if note.type == "task" and (match := TASK_ID.fullmatch(str(note.get("id", ""))))
    }
    stems: dict[str, str] = {}
    for note in vault.iter_notes(vault_root, include_cold=True):
        match = LEGACY_TASK_ID.fullmatch(str(note.get("id", ""))) if note.type == "task" else None
        if not match:
            continue
        number = int(match.group(1))
        old_id, new_id = match.group(0), f"T{number}"
        if number in taken:
            result.skipped.append({"rel": note.rel, "reason": f"{new_id} already exists"})
            continue
        text = note.path.read_text(encoding="utf-8")
        new_text = FRONTMATTER_ID.sub(rf"\g<1>\g<2>{new_id}\g<2>", text, count=1)  # the first `id:` is frontmatter's
        if new_text == text:
            result.skipped.append({"rel": note.rel, "reason": "id line not found in frontmatter"})
            continue
        stem = note.path.stem
        new_stem = new_id + stem.removeprefix(old_id) if stem.startswith(old_id) else stem
        target = note.path.with_name(f"{new_stem}{note.path.suffix}")
        if target != note.path and target.exists():
            result.skipped.append({"rel": note.rel, "reason": f"{target.name} already exists"})
            continue
        note.path.write_text(new_text, encoding="utf-8")
        if target != note.path:
            note.path.rename(target)
            stems[stem] = new_stem
        new_rel = vault.rel_path(vault_root, target)
        result.renamed.append({"from": old_id, "to": new_id, "old_rel": note.rel, "new_rel": new_rel})

    for path in _linking_files(vault_root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # rewriting a file read with replacement characters would destroy it
        new_text = text
        for old, new in sorted(stems.items(), key=lambda item: -len(item[0])):
            new_text = new_text.replace(old, new)
        new_text = blocks.rehash_intact(text, new_text)  # a renamed link is not a hand edit
        rel = vault.rel_path(vault_root, path)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            result.relinked.append(rel)
        if mentions := sorted(set(LEGACY_MENTION.findall(new_text))):
            result.mentions_left.append({"rel": rel, "ids": mentions})
    return result


def _linking_files(vault_root: Path) -> list[Path]:
    found = []
    for root, dirs, files in os.walk(vault_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        found += [Path(root) / name for name in sorted(files) if name.endswith(LINKING_SUFFIXES)]
    return found
