#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Vault health check, with the few fixes that are safe to apply unattended (D30).

  health.py [--today YYYY-MM-DD]          report only
  health.py --fix                         also apply the safe fixes, print what changed

Safe fixes: tag format (lowercase, kebab-case, no '#'), a missing `created` taken from the
note's first commit, and [[link]] letter case when exactly one note matches. Everything else
is reported for a person to decide: broken links (a target that two or more notes link to is
a `wanted_notes` entry instead: a note worth writing, D126), orphans, schema problems, overdue tasks,
tasks stuck in doing or waiting, stale Inbox captures, likely duplicates, credentials in
notes, Templater commands left in a note or a source (`templater_leftovers`, D110), generated
blocks that lost their `@end` line (`broken_blocks`) and notes a fix skipped because they
aren't UTF-8 (`not_utf8`). A note with frontmatter but no `type` gets no fix. An orphan is a
note that no note other than a daily, review or capture note links to (D117); it comes
with proposals for where a link could go: `mentioned_in` (notes that name it in plain
text) and `related` (notes sharing a rare tag or project); nothing is linked for you.
Archive/ and Sources/ are never touched. Prints JSON; the caller commits the files listed under `fixed`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from synapsidianlib import blocks, config, frontmatter, gitops, schema, vault
from synapsidianlib.links import LINK, linked_names, outside_code
from validate import secret_problems

TEMPLATER = re.compile(r"<%[-_*+]?.*?[-_]?%>", re.DOTALL)
ORPHAN_TYPES = {"note", "howto", "decision", "idea", "goal", "project", "person"}
# Generated blocks are rewritten by their skill, so a link added inside one would not last.
GENERATED = blocks.ANY_BLOCK
# Logs and transient notes: a link from one of them doesn't make a note reachable (D117), so
# it neither keeps a note off the orphan list nor is proposed as the place to link one from.
NO_LINK_SOURCES = {"daily", "review", "capture"}
MENTION_MIN_CHARS = 4  # a shorter title matches ordinary words
SUGGESTIONS_PER_ORPHAN = 3
SHARED_KEY_MAX_NOTES = 8  # a tag or project shared by more notes than this says nothing about closeness
INBOX_STALE_DAYS = 7
STUCK_TASK_DAYS = 14  # a doing/waiting task untouched this long has quietly stopped moving
WANTED_MIN_SOURCES = 2  # an unresolved link from this many notes is a wanted note, not a typo


def tag_fixed(tag: object) -> str:
    text = unicodedata.normalize("NFC", str(tag)).strip().lstrip("#").casefold()
    return re.sub(r"[-\s_]+", "-", text).strip("-")


def first_commit_date(vault_root: Path, rel: str) -> dt.date | None:
    out = gitops.git(vault_root, "log", "--diff-filter=A", "--follow", "--format=%cs", "--", rel, check=False)
    dates = [line for line in out.stdout.split() if line]
    return schema.as_date(dates[-1]) if dates else None


def uncommitted(vault_root: Path, folders: list[str]) -> set[str]:
    """Vault-relative paths under `folders` with changes git hasn't committed (modified or untracked)."""
    out = gitops.git(vault_root, "status", "--porcelain", "-z", "--untracked-files=all", "--", *folders, check=False)
    return {unicodedata.normalize("NFC", entry[3:]) for entry in out.stdout.split("\0") if len(entry) > 3}


def templater_commands(text: str) -> list[str]:
    """Templater commands outside code: a template inserted without Templater running, or code
    Templater would run if the note were created again with its trigger on (D110)."""
    found = [m.group(0) for code, part in outside_code(text) if not code for m in TEMPLATER.finditer(part)]
    return [c if len(c) <= 60 else c[:57] + "..." for c in found][:3]


def all_links(note: vault.Note) -> list[str]:
    targets = [m.group(1).strip() for code, part in outside_code(note.body) if not code for m in LINK.finditer(part)]
    for value in (note.meta or {}).values():
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str):
                targets += [m.group(1).strip() for m in LINK.finditer(item)]
    return targets


def prose(note: vault.Note) -> str:
    """What a reader sees as running text: no code, no generated blocks, no existing links."""
    text = GENERATED.sub("", note.body)
    return LINK.sub(" ", "".join(part for code, part in outside_code(text) if not code))


def closeness_keys(note: vault.Note) -> set[str]:
    """Tags and the project, as keys two notes can share."""
    meta = note.meta or {}
    tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
    project = LINK.finditer(str(meta.get("project") or ""))
    return {f"tag:{tag_fixed(t)}" for t in tags} | {f"project:{m.group(1).strip().casefold()}" for m in project}


def link_suggestions(orphans: list[vault.Note], notes: list[vault.Note]) -> dict[str, dict[str, list[str]]]:
    """Orphan rel -> where a link to it could go: notes that name it in plain text (`mentioned_in`)
    and notes that share a rare tag or project with it (`related`). Proposals only, never applied."""
    sources = [n for n in notes if n.meta is not None and n.type not in NO_LINK_SOURCES]
    texts = {n.rel: prose(n).casefold() for n in sources}
    by_key: dict[str, list[str]] = defaultdict(list)
    keys = {n.rel: closeness_keys(n) for n in sources}
    for rel, note_keys in keys.items():
        for key in note_keys:
            by_key[key].append(rel)

    found: dict[str, dict[str, list[str]]] = {}
    for orphan in orphans:
        title = orphan.title.casefold()
        mentioned: list[str] = []
        if len(title) >= MENTION_MIN_CHARS:
            phrase = re.compile(rf"(?<!\w){re.escape(title)}(?!\w)")
            mentioned = [rel for rel, text in texts.items() if rel != orphan.rel and phrase.search(text)]
        score: dict[str, int] = defaultdict(int)
        for key in closeness_keys(orphan):
            if len(by_key.get(key, [])) <= SHARED_KEY_MAX_NOTES:
                for rel in by_key.get(key, []):
                    if rel != orphan.rel and rel not in mentioned:
                        score[rel] += 1
        related = sorted(score, key=lambda rel: (-score[rel], rel))
        entry = {"mentioned_in": mentioned[:SUGGESTIONS_PER_ORPHAN], "related": related[:SUGGESTIONS_PER_ORPHAN]}
        if proposals := {k: v for k, v in entry.items() if v}:
            found[orphan.rel] = proposals
    return found


def fix_link_case(body: str, names: dict[str, list[str]], apply: bool) -> tuple[str, list[dict[str, str]]]:
    """[[links]] whose target exists under another letter case, rewritten to it when `apply`."""
    found: list[dict[str, str]] = []

    def relink(match: re.Match[str]) -> str:
        target, rest = match.group(1).strip(), match.group(2)
        leaf = target.rsplit("/", 1)[-1]
        exact = names.get(leaf.casefold(), [])
        if leaf in exact or len(set(exact)) != 1:
            return match.group(0)
        found.append({"link": target, "should_be": exact[0]})
        return f"[[{target[: len(target) - len(leaf)]}{exact[0]}{rest}]]" if apply else match.group(0)

    return "".join(part if code else LINK.sub(relink, part) for code, part in outside_code(body)), found


def check(vault_root: Path, today: dt.date, apply: bool) -> dict[str, Any]:
    notes = list(vault.iter_notes(vault_root))
    names = linked_names(vault_root)
    s = schema.load(vault_root)
    task_commits: dict[str, dt.date] = {}
    task_dirty: set[str] = set()
    # Tasks may also sit in their project's folder (D102): date them wherever they are.
    task_folders = sorted({n.folder or "." for n in notes if n.type == "task"})
    if task_folders and gitops.is_repo(vault_root):
        task_commits = gitops.last_commit_dates(vault_root, task_folders)
        task_dirty = uncommitted(vault_root, task_folders)
    issues: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fixed: list[dict[str, str]] = []
    reachable: set[str] = set()
    by_title: dict[str, list[str]] = defaultdict(list)

    for note in notes:
        by_title[note.title.casefold()].append(note.rel)
        text_changed = False
        meta = dict(note.meta or {})

        # --- links -------------------------------------------------------------------
        new_body, case_fixes = fix_link_case(note.body, names, apply)
        issues["link_case"] += [{"rel": note.rel, **fix} for fix in case_fixes]
        text_changed = apply and new_body != note.body
        for target in all_links(note):
            leaf = target.rsplit("/", 1)[-1]
            if not names.get(leaf.casefold()):
                issues["broken_links"].append({"rel": note.rel, "link": target})
            elif note.type not in NO_LINK_SOURCES:
                reachable.add(leaf.casefold())

        if note.error or note.meta is None:
            issues["schema"].append({"rel": note.rel, "problems": [note.error or "note has no frontmatter"]})
            continue

        # --- safe frontmatter fixes ----------------------------------------------------
        tags = meta.get("tags")
        if isinstance(tags, list) and tags:
            normal = list(dict.fromkeys(t for t in (tag_fixed(t) for t in tags) if t))
            if normal != tags:
                issues["tag_format"].append({"rel": note.rel, "tags": tags, "should_be": normal})
                if apply:
                    meta["tags"] = normal
                    text_changed = True
        # A note with frontmatter but no type isn't synapsidian's: it gets no `created` (and no `type: null`).
        if schema.is_empty(meta.get("created")) and note.type is not None:
            created = first_commit_date(vault_root, note.rel)
            issues["missing_created"].append({"rel": note.rel, "from_git": created.isoformat() if created else None})
            if apply and created:
                meta = {"type": meta.get("type"), "created": created, **{k: v for k, v in meta.items() if k != "type"}}
                text_changed = True

        if text_changed:
            raw = note.path.read_bytes()
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                # Read with replacement characters; writing that back would destroy the original text.
                issues["not_utf8"].append({"rel": note.rel})
            else:
                before = frontmatter.normalize_newlines(raw.decode("utf-8"))
                # A mechanical rewrite (a link's letter case) keeps an intact hashed block intact.
                note.path.write_text(blocks.rehash_intact(before, frontmatter.dump(meta, new_body)), encoding="utf-8")
                fixed.append({"rel": note.rel, "what": "tags, created or link case"})

        # --- report-only checks -----------------------------------------------------------
        remaining = schema.validate(meta, note.rel, s)
        remaining = [p for p in remaining if "`created`" not in p or not apply]
        if remaining:
            issues["schema"].append({"rel": note.rel, "problems": remaining})
        text = note.path.read_text(encoding="utf-8", errors="replace")
        if secrets := secret_problems(text):
            issues["credentials"].append({"rel": note.rel, "problems": secrets})
        if leftovers := templater_commands(text):
            issues["templater_leftovers"].append({"rel": note.rel, "commands": leftovers})
        if lost := blocks.broken(text):
            issues["broken_blocks"].append({"rel": note.rel, "blocks": lost})
        if note.type == "task" and note.get("status") in ("todo", "doing", "waiting"):
            due = schema.as_date(note.get("due"))
            if due and due < today:
                issues["overdue_tasks"].append({"rel": note.rel, "due": due.isoformat()})
            elif note.get("status") in ("doing", "waiting"):
                # The last commit dates a change; mtime only for uncommitted edits (a clone resets every mtime).
                committed = task_commits.get(note.rel)
                if committed is None or note.rel in task_dirty:
                    changed = dt.datetime.fromtimestamp(note.mtime).date()
                else:
                    changed = committed
                if (today - changed).days > STUCK_TASK_DAYS:
                    issues["stuck_tasks"].append(
                        {"rel": note.rel, "status": note.get("status"), "unchanged_since": changed.isoformat()}
                    )
        if note.folder == "Inbox":
            created = schema.as_date(note.get("created"))
            if created and (today - created).days > INBOX_STALE_DAYS:
                issues["stale_inbox"].append({"rel": note.rel, "created": created.isoformat()})

    # Verbatim copies are never edited, but Templater code in one is the risk D110 describes:
    # it would run if the file were ever created again with Templater's trigger on.
    for path in sorted((vault_root / "Sources").rglob("*.md")) if (vault_root / "Sources").is_dir() else []:
        if found := templater_commands(path.read_text(encoding="utf-8", errors="replace")):
            issues["templater_leftovers"].append({"rel": vault.rel_path(vault_root, path), "commands": found})

    # A target several notes link to is a note waiting to be written, not a mistake (D126).
    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for broken in issues.pop("broken_links", []):
        by_target[broken["link"].rsplit("/", 1)[-1].casefold()].append(broken)
    for links in by_target.values():
        sources = sorted({b["rel"] for b in links})
        if len(sources) >= WANTED_MIN_SOURCES:
            issues["wanted_notes"].append({"link": links[0]["link"], "linked_from": sources})
        else:
            issues["broken_links"] += links

    orphans = [n for n in notes if n.type in ORPHAN_TYPES and n.title.casefold() not in reachable]
    suggestions = link_suggestions(orphans, notes) if orphans else {}
    issues["orphans"] += [{"rel": n.rel, **suggestions.get(n.rel, {})} for n in orphans]
    for rels in by_title.values():
        if len(rels) > 1:
            issues["duplicate_titles"].append({"rels": sorted(rels)})

    found = {k: v for k, v in sorted(issues.items()) if v}
    counts = {k: len(v) for k, v in found.items()}
    return {"ok": True, "checked": len(notes), "counts": counts, "issues": found, "fixed": fixed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    parser.add_argument("--fix", action="store_true", help="apply the safe fixes")
    parser.add_argument("--today")
    args = parser.parse_args()
    vault_root = config.write_vault(args.vault)
    if vault_root is None or not vault_root.is_dir():
        print(json.dumps({"ok": False, "error": "vault not found; run /synapsidian:setup"}))
        sys.exit(2)
    today = schema.as_date(args.today) if args.today else dt.date.today()
    print(json.dumps(check(vault_root, today or dt.date.today(), args.fix), ensure_ascii=False))


if __name__ == "__main__":
    main()
