#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Exact lookups over note frontmatter, and the vault's own commit history.

  query.py notes --type task --where status!=done --where "due<=2026-10-20"
  query.py notes --type task --where source_link=https://... --all      dedup by link, archive included
  query.py notes --type meeting --where event_id=abc123
  query.py commits --since-skill morning --skills evening,save          "Written overnight"
  query.py stale --days 30 --limit 3 [--remember]                       "(as of D)" facts to re-check
  query.py resurface --days 60 --limit 1 [--remember]                   an old note worth a second look
  query.py watched                                                      watched research due for a refresh

Operators: = != < <= > >= ~ (contains, case-insensitive). Dates compare as dates, a missing
field never matches a comparison (so `due<=X` skips undated tasks), and `field=` matches empty.
Prints JSON.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from synapsidianlib import blocks, config, gitops, schema, vault

CONDITION = re.compile(r"^(?P<field>[A-Za-z_][\w.]*)\s*(?P<op>!=|<=|>=|=|<|>|~)\s*(?P<value>.*)$")


def as_comparable(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and (parsed := schema.as_date(value)):
        return parsed
    return value


def text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    if isinstance(value, dt.date):
        return value.isoformat()
    return "" if value is None else str(value)


def matches(note: vault.Note, field: str, op: str, raw: str) -> bool:
    value = note.title if field == "title" else note.get(field)
    if op == "~":
        return raw.casefold() in text(value).casefold()
    if op in ("=", "!="):
        equal = text(value).strip() == raw.strip() or (raw == "" and schema.is_empty(value))
        if isinstance(value, list):
            equal = equal or raw.strip() in [text(v).strip() for v in value]
        return equal if op == "=" else not equal
    if schema.is_empty(value):
        return False
    left, right = as_comparable(value), as_comparable(raw)
    try:
        return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]
    except TypeError:
        return False


def cmd_notes(vault_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    conditions = []
    for raw in args.where:
        match = CONDITION.match(raw)
        if not match:
            raise ValueError(f"can't read condition {raw!r}; use field=value, field!=value, field<=value, ...")
        conditions.append((match["field"], match["op"], match["value"]))
    rows = []
    for note in vault.iter_notes(vault_root, include_cold=args.all):
        if args.type and note.type != args.type:
            continue
        if args.folder and not (note.folder + "/").startswith(args.folder.rstrip("/") + "/"):
            continue
        if all(matches(note, *c) for c in conditions):
            rows.append(note)
    rows.sort(key=lambda n: (text(as_comparable(n.get(args.sort))) if args.sort else "", n.rel))
    return {
        "ok": True,
        "count": len(rows),
        "truncated": len(rows) > args.limit,  # `notes` holds the first --limit of `count`
        "notes": [
            {
                "rel": n.rel,
                "path": str(n.path),
                "title": n.title,
                "modified": dt.datetime.fromtimestamp(n.mtime).astimezone().isoformat(timespec="minutes"),
                **{k: text(v) if isinstance(v, dt.date) else v for k, v in (n.meta or {}).items()},
            }
            for n in rows[: args.limit]
        ],
    }


SINCE_SKILL_MAX_DAYS = 7  # a long weekend and more; past that, the `since_skill` run is missing, not old


AS_OF = re.compile(r"\(as of (\d{4}-\d{2}-\d{2})\)")
CODE = re.compile(r"^(```|~~~).*?^\1|`[^`\n]+`", re.M | re.S)
NO_CHECKIN_TYPES = {"daily", "review", "capture", "source"}
CHECKIN_STATE = "checkin.json"


def cmd_stale(vault_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Facts stamped `(as of D)` more than `--days` ago, oldest first, for a "Still true?" check (D128).

    With `--remember` the ones returned are recorded in `<vault>/.git/synapsidian/checkin.json` and
    left out for `--quiet-days`, so each morning asks about different facts.
    """
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    state_path = config.state_dir(vault_root) / CHECKIN_STATE
    try:
        asked: dict[str, str] = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        asked = {}
    found = []
    for note in vault.iter_notes(vault_root):
        if note.type in NO_CHECKIN_TYPES or note.meta is None:
            continue
        # Code and generated blocks don't count: a block's facts are rewritten by its own skill.
        prose = blocks.ANY_BLOCK.sub("", CODE.sub("", note.body))
        for line in prose.splitlines():
            for match in AS_OF.finditer(line):
                stamped = schema.as_date(match[1])
                if stamped is None or (today - stamped).days < args.days:
                    continue
                fact = " ".join(line.strip().lstrip("-*> ").split())
                key = f"{note.rel}#{fact}"
                last = schema.as_date(asked.get(key))
                if last and (today - last).days < args.quiet_days:
                    continue
                found.append({"rel": note.rel, "title": note.title, "fact": fact[:300], "as_of": match[1],
                              "age_days": (today - stamped).days, "key": key})  # fmt: skip
    found.sort(key=lambda f: (-f["age_days"], f["rel"]))
    picked = found[: args.limit]
    if args.remember and picked:
        asked |= {f["key"]: today.isoformat() for f in picked}
        state_path.write_text(json.dumps(asked, ensure_ascii=False, indent=0), encoding="utf-8")
    return {"ok": True, "count": len(found), "facts": [{k: v for k, v in f.items() if k != "key"} for f in picked]}


RESURFACE_TYPES = {"note", "howto", "decision"}
RESURFACE_STATE = "resurfaced.json"
LINK = re.compile(r"\[\[([^\[\]|#\n]+)")


def cmd_resurface(vault_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Old knowledge worth a second look (D132): notes, how-tos and live decisions unchanged for
    `--days`, the most linked-to first, none shown again within `--quiet-days` (with `--remember`).

    Unchanged means no commit touched the note in that time (mtime only for one never committed:
    a clone resets mtimes). Re-reading what one knew is how notes stay alive, the idea behind
    Readwise's daily review and evergreen-note maintenance.
    """
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    state_path = config.state_dir(vault_root) / RESURFACE_STATE
    try:
        shown: dict[str, str] = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        shown = {}
    notes = list(vault.iter_notes(vault_root))
    inbound: dict[str, int] = {}
    for note in notes:
        for target in {m[1].strip().rsplit("/", 1)[-1].casefold() for m in LINK.finditer(note.body)}:
            inbound[target] = inbound.get(target, 0) + 1
    candidates = [
        n for n in notes
        if n.type in RESURFACE_TYPES and str(n.get("status", "")) not in ("superseded", "rejected", "deprecated")
    ]  # fmt: skip
    changed = gitops.last_commit_dates(vault_root, ["."]) if gitops.is_repo(vault_root) else {}
    found = []
    for note in candidates:
        last = changed.get(note.rel) or dt.datetime.fromtimestamp(note.mtime).date()
        seen = schema.as_date(shown.get(note.rel))
        if (today - last).days < args.days or (seen and (today - seen).days < args.quiet_days):
            continue
        found.append(
            {
                "rel": note.rel,
                "title": note.title,
                "type": note.type,
                "summary": note.get("summary"),
                "unchanged_since": last.isoformat(),
                "linked_from": inbound.get(note.title.casefold(), 0),
            }
        )
    found.sort(key=lambda f: (-f["linked_from"], f["unchanged_since"], f["rel"]))
    picked = found[: args.limit]
    if args.remember and picked:
        shown |= {f["rel"]: today.isoformat() for f in picked}
        state_path.write_text(json.dumps(shown, ensure_ascii=False, indent=0), encoding="utf-8")
    return {"ok": True, "count": len(found), "notes": picked}


WATCH_DAYS = {"weekly": 7, "monthly": 30, "quarterly": 91}


def cmd_watched(vault_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Watched research dossiers due for a refresh (D134): `watch` set, and its interval passed
    since `refreshed` (or `created`). Oldest first."""
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    due = []
    for note in vault.iter_notes(vault_root):
        days = WATCH_DAYS.get(str(note.get("watch") or ""))
        if note.type != "research" or days is None:
            continue
        last = schema.as_date(note.get("refreshed")) or schema.as_date(note.get("created"))
        if last is None or (today - last).days >= days:
            since = last.isoformat() if last else None
            due.append({"rel": note.rel, "title": note.title, "question": note.get("question"),
                        "watch": note.get("watch"), "since": since})  # fmt: skip
    due.sort(key=lambda d: (d["since"] or "", d["rel"]))
    return {"ok": True, "due": due}


def cmd_commits(vault_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Commits by the given skills since the last commit by `since_skill` made before today.

    `since_skill`'s own commits from today don't end the window, so running the morning twice
    lists the same overnight work both times. A run whose files Obsidian Git committed first
    (D85) has no `synapsidian(...)` commit; `synapsidian commit` logged it in the state dir, and it counts
    as a commit of its skill here (`swept: true`, D129). With no earlier `since_skill` run at
    all, the window stops after SINCE_SKILL_MAX_DAYS.
    """
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    wanted = {s.strip() for s in args.skills.split(",") if s.strip()}
    swept = []
    for row in _jsonl(config.state_dir(vault_root) / gitops.SWEPT_LOG):
        try:
            at = dt.datetime.fromisoformat(str(row.get("at"))).astimezone()
        except ValueError:
            continue
        swept.append((at, row))
    start = dt.datetime.combine(today - dt.timedelta(days=SINCE_SKILL_MAX_DAYS), dt.time.min).astimezone()
    runs = [at for at, row in swept if row.get("skill") == args.since_skill and at.date() < today]
    start = max([start, *runs])

    picked = []
    log = gitops.git(vault_root, "log", "--format=%H%x09%cI%x09%s", "-500", check=False).stdout.splitlines()
    for line in log:
        sha, when, subject = [*line.split("\t", 2), "", ""][:3]
        skill = subject.split("(", 1)[1].split(")", 1)[0] if subject.startswith("synapsidian(") else None
        try:
            moment = dt.datetime.fromisoformat(when).astimezone()
        except ValueError:
            continue
        if moment <= start:
            break
        if skill == args.since_skill and moment.date() < today:
            start = moment
            break
        if skill in wanted:
            files = gitops.git(vault_root, "show", "--format=", "--name-only", sha).stdout.split("\n")
            picked.append({"sha": sha[:7], "when": when, "subject": subject, "files": [f for f in files if f]})
    for at, row in swept:
        if row.get("skill") in wanted and at >= start:  # seconds resolution: the same second counts
            shas = row.get("shas") or [""]
            picked.append({"sha": str(shas[0])[:7], "when": at.isoformat(), "subject": str(row.get("message")),
                           "files": list(row.get("files") or []), "swept": True})  # fmt: skip
    picked.sort(key=lambda c: dt.datetime.fromisoformat(c["when"]), reverse=True)
    return {"ok": True, "since_last": args.since_skill, "commits": picked}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    sub = parser.add_subparsers(dest="cmd", required=True)
    notes = sub.add_parser("notes")
    notes.add_argument("--type")
    notes.add_argument("--folder")
    notes.add_argument("--where", action="append", default=[], metavar="COND")
    notes.add_argument("--all", action="store_true", help="include Archive/ and Sources/")
    notes.add_argument("--sort", help="frontmatter field to sort by")
    notes.add_argument("--limit", type=int, default=200)
    commits = sub.add_parser("commits")
    commits.add_argument("--since-skill", default="morning")
    commits.add_argument("--skills", default="evening,save")
    commits.add_argument("--today", help="YYYY-MM-DD (default: today)")
    stale = sub.add_parser("stale")
    stale.add_argument("--days", type=int, default=30, help="stamped at least this many days ago")
    stale.add_argument("--limit", type=int, default=3)
    stale.add_argument("--remember", action="store_true", help="record what was returned, so it rotates")
    stale.add_argument("--quiet-days", type=int, default=14, help="leave out facts returned this recently")
    stale.add_argument("--today", help="YYYY-MM-DD (default: today)")
    resurface = sub.add_parser("resurface")
    resurface.add_argument("--days", type=int, default=60, help="unchanged for at least this many days")
    resurface.add_argument("--limit", type=int, default=1)
    resurface.add_argument("--remember", action="store_true", help="record what was returned, so it rotates")
    resurface.add_argument("--quiet-days", type=int, default=90, help="leave out notes returned this recently")
    resurface.add_argument("--today", help="YYYY-MM-DD (default: today)")
    watched = sub.add_parser("watched")
    watched.add_argument("--today", help="YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    vault_root = config.vault_path(args.vault)
    if vault_root is None or not vault_root.is_dir():
        print(json.dumps({"ok": False, "error": "vault not found; run /synapsidian:setup"}))
        sys.exit(2)
    try:
        commands = {
            "notes": cmd_notes,
            "commits": cmd_commits,
            "stale": cmd_stale,
            "resurface": cmd_resurface,
            "watched": cmd_watched,
        }
        result = commands[args.cmd](vault_root, args)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(2)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
