#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""PreToolUse hook: let Claude edit vault notes without a prompt each time (D7).

Allows Write/Edit on .md, .base and .canvas files inside the vault. Some of those files are
code or instructions rather than notes, and an unattended run that read an injected line
in a web page or transcript must not change them on its own (D120):

- no decision (Claude Code's own rules apply): `.git`, `.obsidian`, `.trash` and `.claude`
  (skills, agents and commands Claude Code loads in sessions started in the vault);
- ask: `CLAUDE.md`, `CLAUDE.local.md` and `AGENTS.md` anywhere (instructions every session in
  that folder loads), `About.md` (its Rules reach every session through the brief), `Templates/`
  (Templater runs the code in a template), `.synapsidian/` (installed schema extensions), and
  existing files in `Sources/` (immutable copies).

Turned off by the plugin option `auto_approve_vault_edits`. Whatever that option says, a
Write/Edit under a path listed in About.md's `protected` field asks the user first (D94).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePosixPath

from synapsidianlib import config, frontmatter
from synapsidianlib.about import is_protected, protected_paths

ALLOWED_SUFFIXES = {".md", ".base", ".canvas"}
NEVER_DIRS = {".git", ".obsidian", ".trash", ".claude"}
OFF_VALUES = {"false", "0", "no", "off"}
INSTRUCTION_FILES = {"claude.md", "claude.local.md", "agents.md"}
ASK_TOP = {  # top-level names, case-folded
    "about.md": "About.md holds the user's own rules, which every session reads.",
    "templates": "Templater runs the code in a template when a note is created from it.",
    ".synapsidian": ".synapsidian/ holds the schema extensions synapsidian setup installs.",
}


def protected_in(vault_root: Path) -> list[PurePosixPath]:
    try:
        text = (vault_root / "About.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return protected_paths((frontmatter.parse(text).meta or {}).get("protected"))


def ask(reason: str) -> dict[str, object]:
    return {"permissionDecision": "ask", "permissionDecisionReason": f"synapsidian: {reason}"}


def decide(payload: dict[str, object], vault_root: Path, *, auto_approve: bool = True) -> dict[str, object] | None:
    if payload.get("tool_name") not in ("Write", "Edit") or config.too_broad(vault_root):
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")  # type: ignore[union-attr]
    if not isinstance(raw, str):
        return None
    path = config.true_case(Path(raw).expanduser())
    try:
        rel = path.relative_to(vault_root)
    except ValueError:
        return None
    if NEVER_DIRS & {part.casefold() for part in rel.parts}:
        return None
    if entry := is_protected(PurePosixPath(rel.as_posix()), protected_in(vault_root)):
        return ask(f"About.md marks {entry} as protected.")
    if path.name.casefold() in INSTRUCTION_FILES:
        return ask(f"{path.name} is loaded as instructions by sessions started in that folder.")
    if rel.parts and (reason := ASK_TOP.get(rel.parts[0].casefold())):
        return ask(reason)
    if not auto_approve or path.suffix not in ALLOWED_SUFFIXES:
        return None
    if rel.parts and rel.parts[0] == "Sources" and path.exists():
        return ask("Sources/ holds immutable copies of ingested material.")
    return {
        "permissionDecision": "allow",
        "permissionDecisionReason": "synapsidian: note inside the vault (auto_approve_vault_edits).",
    }


def main() -> None:
    auto_approve = (
        os.environ.get("CLAUDE_PLUGIN_OPTION_AUTO_APPROVE_VAULT_EDITS", "true").strip().lower() not in OFF_VALUES
    )
    vault_root = config.vault_path()
    if vault_root is None:
        return
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    decision = decide(payload, vault_root, auto_approve=auto_approve)
    if decision:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **decision}}))


if __name__ == "__main__":
    main()
