#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Replace or read a generated block in a note, leaving everything else byte for byte.

A block is the text between `<!-- @generated:<name> -->` and the next `<!-- @end -->`.

  block.py set --vault V --file Daily/2026-10-13.md --name brief < content.md
  block.py get --vault V --file Daily/2026-10-13.md --name brief
  block.py set --file Daily/2026-10-14.md --name plan --section "Plan" < bullets.md
  block.py set --file "Notes/Garden.md" --name facts --section Facts --before Log --hash < facts.md
  block.py set --file "Notes/Garden layout.md" --name beds --hash < text.md
  block.py check --file "Notes/Garden layout.md"

With --hash the opening marker carries a hash of the content it wrote
(`<!-- @generated:structure sha=0123456789ab -->`). A later `set` on that block refuses
(exit 4, current content returned) when the content no longer matches the hash, i.e.
someone edited it by hand; --force overwrites anyway. Hashed blocks stay hashed. `check`
lists every block with `ok`, `edited`, `unhashed` or `broken`.

A block whose `<!-- @end -->` line is gone is `broken`: `set` and `get` refuse it (exit 5)
rather than guess where it ended, since a guess could replace the user's text.

`set` refuses content that looks like a credential (exit 2, `problems`), as `note new` does.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from synapsidianlib import config, gitops, vault
from synapsidianlib.blocks import ANY_BLOCK, END, INNER, OPEN, broken, digest
from synapsidianlib.credentials import secret_problems
from synapsidianlib.sections import append_to_section


class EditedBlock(Exception):
    def __init__(self, current: str) -> None:
        super().__init__("edited by hand")
        self.current = current


class BrokenBlock(Exception):
    pass


def block_re(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"({re.escape(OPEN)}{re.escape(name)})(?: sha=([0-9a-f]{{12}}))?( -->\n)({INNER})(^{re.escape(END)})",
        re.S | re.M,
    )


def replace_block(text: str, name: str, content: str, *, hashed: bool = False, force: bool = False) -> str:
    if name in broken(text):
        raise BrokenBlock(name)
    match = block_re(name).search(text)
    if not match:
        raise KeyError(name)
    stored, current = match.group(2), match.group(4)
    if stored and not force and digest(current) != stored:
        raise EditedBlock(current)
    inner = content.strip("\n")
    inner = f"{inner}\n" if inner else ""
    tag = f" sha={digest(inner)}" if hashed or stored else ""
    return f"{text[: match.start()]}{match.group(1)}{tag}{match.group(3)}{inner}{match.group(5)}{text[match.end() :]}"


def add_section(
    text: str, title: str, name: str, content: str, *, hashed: bool = False, before: str | None = None
) -> str:
    """Put an empty generated block at the end of `## title` (the section is added before the
    `before` section, else at the end, when missing), then fill it."""
    joined = append_to_section(text, title, f"<!-- @generated:{name} -->\n{END}\n", before)
    return replace_block(joined, name, content, hashed=hashed)


def read_block(text: str, name: str) -> str:
    if name in broken(text):
        raise BrokenBlock(name)
    match = block_re(name).search(text)
    if not match:
        raise KeyError(name)
    return match.group(4)


def check_blocks(text: str) -> list[dict[str, str]]:
    def status(stored: str | None, inner: str) -> str:
        if not stored:
            return "unhashed"
        return "ok" if digest(inner) == stored else "edited"

    found = [{"name": m.group(1), "status": status(m.group(2), m.group(3))} for m in ANY_BLOCK.finditer(text)]
    return found + [{"name": name, "status": "broken"} for name in broken(text)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["set", "get", "check"])
    parser.add_argument("--vault")
    parser.add_argument("--file", required=True, help="vault-relative path")
    parser.add_argument("--name")
    parser.add_argument("--section", metavar="TITLE", help="set: put a missing block at the end of '## TITLE'")
    parser.add_argument("--before", metavar="TITLE", help="set: where a missing '## TITLE' goes (default: the end)")
    parser.add_argument("--hash", action="store_true", help="set: protect the block against silent overwrites")
    parser.add_argument("--force", action="store_true", help="set: overwrite a hashed block edited by hand")
    args = parser.parse_args()
    if args.cmd != "check" and not args.name:
        parser.error("--name is required for set and get")

    vault_root = config.write_vault(args.vault)
    target = (vault_root / args.file).resolve() if vault_root else Path(args.file)
    allowed = vault.is_inside if args.cmd != "set" else vault.is_editable_note
    if vault_root is None or not allowed(vault_root, target) or not target.is_file():
        print(json.dumps({"ok": False, "error": f"{args.file} is not a note inside the vault synapsidian may change"}))
        sys.exit(2)

    if args.cmd == "set":
        if vault.rel_path(vault_root, target).startswith("Sources/"):
            print(json.dumps({"ok": False, "error": "a source's body is never edited (D75)"}))
            sys.exit(2)
        content = sys.stdin.read()
        # Devlog and brief blocks are written from session transcripts, like the notes `note new` screens.
        if problems := secret_problems(content):
            error = "the text looks like it holds a credential; nothing written"
            print(json.dumps({"ok": False, "error": error, "problems": problems}))
            sys.exit(2)
        # Two runs writing blocks of one note at once (the morning and the stand-up both fill
        # today's daily note) would each write back the file as they read it: one block lost.
        with gitops.vault_lock(config.state_dir(vault_root), name="notes.lock"):
            update(target, args, content)
        return
    text = target.read_text(encoding="utf-8")
    if args.cmd == "check":
        print(json.dumps({"ok": True, "rel": args.file, "blocks": check_blocks(text)}))
        return
    try:
        sys.stdout.write(read_block(text, args.name))
    except KeyError:
        print(json.dumps({"ok": False, "error": f"no @generated:{args.name} block in {args.file}"}))
        sys.exit(3)
    except BrokenBlock:
        print(json.dumps({"ok": False, "error": broken_message(args), "name": args.name}))
        sys.exit(5)


def broken_message(args: argparse.Namespace) -> str:
    return (
        f"the @generated:{args.name} block in {args.file} has lost its `{END}` line; nothing written. "
        "Put the line back where the block should end, then run this again."
    )


def update(target: Path, args: argparse.Namespace, content: str) -> None:
    text = target.read_text(encoding="utf-8")
    try:
        try:
            updated = replace_block(text, args.name, content, hashed=args.hash, force=args.force)
        except KeyError:
            if not args.section:
                raise
            updated = add_section(text, args.section, args.name, content, hashed=args.hash, before=args.before)
    except KeyError:
        print(json.dumps({"ok": False, "error": f"no @generated:{args.name} block in {args.file}"}))
        sys.exit(3)
    except EditedBlock as exc:
        print(json.dumps({"ok": False, "error": "edited by hand", "name": args.name, "current": exc.current}))
        sys.exit(4)
    except BrokenBlock:
        print(json.dumps({"ok": False, "error": broken_message(args), "name": args.name}))
        sys.exit(5)
    if updated != text:
        target.write_text(updated, encoding="utf-8")
    print(json.dumps({"ok": True, "rel": args.file, "changed": updated != text}))


if __name__ == "__main__":
    main()
