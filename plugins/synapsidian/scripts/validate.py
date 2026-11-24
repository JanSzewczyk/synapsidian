#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Check vault notes against schema/types.yaml. Warns, never blocks (D43).

validate.py --hook            PostToolUse hook: reads the hook JSON on stdin
validate.py [--vault V] FILE  check files (vault-relative or absolute)
validate.py [--vault V] --all check every note
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from synapsidianlib import config, schema, vault
from synapsidianlib.credentials import secret_problems

# Not checked: immutable sources, archived notes, plugin/app folders.
EXEMPT_TOP = frozenset({"Sources", "Archive", *vault.SKIP_DIRS})


def check(vault_root: Path, path: Path) -> list[str] | None:
    """Issues for one file, or None when the file is out of scope."""
    if path.suffix != ".md" or path.name.endswith(vault.NOT_NOTE_SUFFIXES):
        return None
    if not path.is_file() or not vault.is_inside(vault_root, path):
        return None
    rel = vault.rel_path(vault_root, path.resolve())
    if rel.split("/", 1)[0] in EXEMPT_TOP or any(part.startswith(".") for part in rel.split("/")):
        return None
    note = vault.read_note(vault_root, path.resolve())
    secrets = secret_problems(path.read_text(encoding="utf-8", errors="replace"))
    if note.error:
        return [note.error, *secrets]
    return [*schema.validate(note.meta, rel, schema.load(vault_root)), *secrets]


def hook() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    vault_root = config.vault_path()
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if vault_root is None or not file_path:
        return
    issues = check(vault_root, Path(file_path))
    if not issues:
        return
    rel = vault.rel_path(vault_root, Path(file_path).resolve())
    message = (
        f"synapsidian: `{rel}` does not match the vault schema: "
        + "; ".join(issues)
        + ". Fix the frontmatter (see the synapsidian plugin's schema/types.yaml) before moving on."
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--vault")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()

    if args.hook:
        try:
            hook()
        except Exception as exc:  # the validator must never break a write
            print(f"synapsidian validate failed: {exc}", file=sys.stderr)
        return

    vault_root = config.vault_path(args.vault)
    if vault_root is None or not vault_root.is_dir():
        print(json.dumps({"ok": False, "error": "vault not found"}))
        sys.exit(2)
    paths = (
        [n.path for n in vault.iter_notes(vault_root, include_cold=True)]
        if args.all
        else [p if (p := Path(f)).is_absolute() else vault_root / f for f in args.files]
    )
    report = {}
    for path in paths:
        issues = check(vault_root, path)
        if issues:
            report[vault.rel_path(vault_root, path.resolve())] = issues
    print(json.dumps({"ok": not report, "checked": len(paths), "issues": report}, ensure_ascii=False))
    sys.exit(0 if not report else 1)


if __name__ == "__main__":
    main()
