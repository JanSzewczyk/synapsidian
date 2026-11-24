#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""UserPromptSubmit hook: a prompt starting with `>>` goes to Inbox/ as is, with no model turn (D137).

`hooks/capture.sh` runs this only for such a prompt, so other prompts never start uv. The
text after `>>` becomes a capture note, as `/synapsidian:capture` writes one (D51: raw, no linking),
committed as `synapsidian(capture): ...`, and the prompt is blocked: Claude never sees it and no
tokens are spent. The block message says where it went and leaves the text out.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path, PurePosixPath

from approve import protected_in
from synapsidianlib import config, frontmatter, gitops, schema, vault
from synapsidianlib.about import is_protected
from validate import secret_problems

PREFIX = ">>"
URL = re.compile(r"https?://\S+")
TITLE_WORDS = 6


def title_of(text: str) -> str:
    """The first words of the first line, URLs left out; the URL's host when there is nothing else."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    words = URL.sub(" ", first).split()[:TITLE_WORDS]
    title = schema.clean_title(" ".join(words))
    if not title and (url := URL.search(text)):
        title = schema.clean_title(re.sub(r"^https?://(www\.)?", "", url.group(0)).split("/")[0])
    return title[:80].strip() or "capture"


def capture(vault_root: Path, text: str, now: dt.datetime) -> str:
    """Write and commit the capture; the note's vault-relative path."""
    s = schema.load(vault_root)
    note_type = s.types["capture"]
    meta: dict[str, object] = {"type": "capture", "created": now.date()}
    if url := URL.search(text):
        meta["source_url"] = url.group(0)
    name = schema.filename_for(note_type, meta, title_of(text), now)
    folder = vault_root / note_type.folder
    folder.mkdir(parents=True, exist_ok=True)
    with gitops.vault_lock(config.state_dir(vault_root), name="notes.lock"):
        for n in range(1, 50):
            target = folder / (f"{name}.md" if n == 1 else f"{name} ({n}).md")
            try:
                with target.open("x", encoding="utf-8") as handle:
                    handle.write(frontmatter.dump(meta, text.strip() + "\n"))
                break
            except FileExistsError:
                continue
        else:
            raise RuntimeError(f"too many captures named {name!r}")
    rel = vault.rel_path(vault_root, target)
    if gitops.is_repo(vault_root):
        with gitops.vault_lock(config.state_dir(vault_root)):
            gitops.commit(vault_root, [rel], f"synapsidian(capture): {target.stem}")
    return rel


def block(reason: str) -> None:
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": reason,
                "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "suppressOriginalPrompt": True},
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    prompt = str(payload.get("prompt") or "")
    if not prompt.lstrip().startswith(PREFIX):
        return
    text = prompt.lstrip()[len(PREFIX) :].strip()
    vault_root = config.vault_path()
    if not text:
        block("synapsidian: nothing after >> to capture.")
        return
    if vault_root is None or not vault_root.is_dir():
        block("synapsidian: no vault is set up, so nothing was captured. Run /synapsidian:setup.")
        return
    if problems := secret_problems(text):
        block(f"synapsidian: not captured, the text {problems[0]}.")
        return
    if is_protected(PurePosixPath("Inbox"), protected_in(vault_root)):
        block("synapsidian: About.md protects Inbox/, so nothing was captured.")
        return
    try:
        rel = capture(vault_root, text, dt.datetime.now())
    except (OSError, RuntimeError, gitops.LockTimeout) as exc:
        block(f"synapsidian: capture failed ({exc}); the text was not saved.")
        return
    block(f"Captured to {rel} (not sent to Claude). /synapsidian:save inbox files it later.")


if __name__ == "__main__":
    main()
