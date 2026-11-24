#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""How a project stands: what closed in a window, what is under way or waiting, its milestones (D149).

  synapsidian query notes --limit 100000 | progress.py --project "Web app"          since the last status
  synapsidian query notes --limit 100000 | progress.py --project "Web app" --since 2026-10-27 --until 2026-10-31
  ... [--today YYYY-MM-DD] [--markdown]

Reads `synapsidian query notes` JSON on stdin. Without `--since` the window starts the day after the
newest status line (`- YYYY-MM-DD: status: ...`) of the hub's `## Log`, so what the last status
reported isn't reported again, or on the day the hub was made when it has none; other Log lines
(a refresh, a milestone) don't move it. Both ends count. Closed in the window: tasks, changes and
milestones by `done_on`, and accepted decisions by `created`, since a decision keeps no date of
its acceptance.

Prints JSON: `since`, `until`, `closed`, `in_progress` (tasks doing or waiting), `blocked` (open
tasks waiting on an open task, of any project), `milestones` (open ones with `done`/`total` tasks and
`days_to_target`, negative when past), `open` (every open task, milestone, change and proposed
decision) and `summary`, one Markdown line; `--markdown` prints only that line. Exit 2 = bad input
or an unknown project.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from flows import OPEN_TASK, blockers, task_order
from projects import fail, link_title

OPEN_MILESTONE = {"planned", "active"}
OPEN_CHANGE = {"proposed", "doing"}
STATUS_LINE = re.compile(r"^[-*] +(\d{4}-\d{2}-\d{2}): *status\b", re.M)


def day(value: object) -> str:
    """The `YYYY-MM-DD` of a date field, or "" when it has none."""
    text = str(value or "")
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else ""


def after_last_status(hub: dict[str, Any]) -> str:
    """The day after the newest status line of the hub's `## Log`, or ""."""
    try:
        text = Path(hub["path"]).read_text(encoding="utf-8")
    except (KeyError, OSError):
        return ""
    section = re.search(r"^## Log[ \t]*\n(.*?)(?=^#{1,2} |\Z)", text, re.M | re.S)
    last = max(STATUS_LINE.findall(section.group(1)), default="") if section else ""
    return (dt.date.fromisoformat(last) + dt.timedelta(days=1)).isoformat() if last else ""


def links(titles: list[str]) -> str:
    return ", ".join(f"[[{t}]]" for t in titles)


def count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def report(notes: list[dict[str, Any]], hub: dict[str, Any], since: str, until: str, today: dt.date) -> dict[str, Any]:
    mine = [n for n in notes if link_title(n.get("project")).casefold() == hub["title"].casefold()]

    def of(kind: str) -> list[dict[str, Any]]:
        return sorted((n for n in mine if n.get("type") == kind), key=task_order)

    def closed(kind: str, field: str = "done_on", status: str = "done") -> list[dict[str, str]]:
        return [{"title": n["title"], field: day(n.get(field))} for n in of(kind)
                if n.get("status") == status and since <= day(n.get(field)) <= until]  # fmt: skip

    tasks = of("task")
    open_tasks = [t for t in tasks if t.get("status") in OPEN_TASK]
    # A blocker may be another project's task, as in the core brief.
    open_titles = {n["title"].casefold(): n["title"] for n in notes
                   if n.get("type") == "task" and n.get("status") in OPEN_TASK}  # fmt: skip
    blocked = []
    for task in open_tasks:
        waits_on = [open_titles[b.casefold()] for b in blockers(task) if b.casefold() in open_titles]
        if waits_on:
            blocked.append({"title": task["title"], "status": task["status"], "blocked_by": waits_on})

    milestones = []
    for m in of("milestone"):
        if m.get("status") not in OPEN_MILESTONE:
            continue
        own = [t for t in tasks if link_title(t.get("milestone")).casefold() == m["title"].casefold()
               and t.get("status") != "dropped"]  # fmt: skip
        target = day(m.get("target"))
        milestones.append({
            "title": m["title"], "status": m["status"], "target": target or None,
            "done": sum(t.get("status") == "done" for t in own), "total": len(own),
            "days_to_target": (dt.date.fromisoformat(target) - today).days if target else None,
        })  # fmt: skip
    milestones.sort(key=lambda m: (m["target"] or "9999", m["title"]))

    def brief(note: dict[str, Any]) -> dict[str, str]:
        return {"title": note["title"], "status": note["status"]}

    result = {
        "project": hub["title"],
        "since": since,
        "until": until,
        "closed": {
            "tasks": closed("task"),
            "milestones": closed("milestone"),
            "changes": closed("change"),
            "decisions": closed("decision", "created", "accepted"),
        },
        "in_progress": [brief(t) for t in open_tasks if t["status"] in {"doing", "waiting"}],
        "blocked": blocked,
        "milestones": milestones,
        "open": {
            "tasks": [{**brief(t), "milestone": link_title(t.get("milestone")) or None} for t in open_tasks],
            "milestones": [brief(m) for m in milestones],
            "changes": [brief(c) for c in of("change") if c.get("status") in OPEN_CHANGE],
            "decisions": [{"title": d["title"]} for d in of("decision") if d.get("status") == "proposed"],
        },
    }
    result["summary"] = summary(result)
    return result


def summary(r: dict[str, Any]) -> str:
    """One line for a review: what closed, what is under way, the next milestone."""
    closed = r["closed"]
    parts = [count(len(closed["tasks"]), "task") + " done"] if closed["tasks"] else []
    parts += [f"{links([m['title'] for m in closed['milestones']])} reached"] if closed["milestones"] else []
    parts += [f"{links([c['title'] for c in closed['changes']])} done"] if closed["changes"] else []
    parts += [count(len(closed["decisions"]), "decision") + " accepted"] if closed["decisions"] else []
    line = f"[[{r['project']}]]: " + (", ".join(parts) if parts else "nothing closed")
    now = [f"{len(r['in_progress'])} in progress"] if r["in_progress"] else []
    now += [f"{len(r['blocked'])} blocked"] if r["blocked"] else []
    if now:
        line += "; " + ", ".join(now)
    if r["milestones"]:
        m = r["milestones"][0]
        when = ("no target" if m["days_to_target"] is None
                else f"{m['days_to_target']} days left" if m["days_to_target"] >= 0
                else f"{-m['days_to_target']} days past target")  # fmt: skip
        line += f"; next [[{m['title']}]] {m['done']}/{m['total']}, {when}"
    return line


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="the project's hub title")
    parser.add_argument("--since", type=dt.date.fromisoformat, help="first day (default: after the last status)")
    parser.add_argument("--until", type=dt.date.fromisoformat, help="last day (default: --today)")
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help="for days to target")
    parser.add_argument("--markdown", action="store_true", help="print only the summary line")
    args = parser.parse_args()
    try:
        notes = json.loads(sys.stdin.read() or "{}").get("notes") or []
    except (json.JSONDecodeError, AttributeError) as exc:
        fail(2, f"stdin is not `synapsidian query notes` JSON: {exc}")
    hub = next((n for n in notes if n.get("type") == "project"
                and str(n.get("title", "")).casefold() == args.project.casefold()), None)  # fmt: skip
    if hub is None:
        fail(2, f"no project titled {args.project!r} in the query (pass `synapsidian query notes --limit 100000`)")
    since = args.since.isoformat() if args.since else after_last_status(hub) or day(hub.get("created"))
    until = (args.until or args.today).isoformat()
    result = report(notes, hub, since, until, args.today)
    if args.markdown:
        print(result["summary"])
        return
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
