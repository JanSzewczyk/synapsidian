#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Mermaid diagrams of a project's order of work (D146), for generated blocks.

  synapsidian query notes --limit 100000 | flows.py --project "Web app"                       roadmap
  synapsidian query notes --limit 100000 | flows.py --project "Web app" --milestone "Web app beta"
  synapsidian query notes --limit 100000 | flows.py --project "Web app" --change "2026-11-03 Move to API v2"
  ... [--markdown]

Reads `synapsidian query notes` JSON on stdin. Without `--milestone` or `--change` it draws the hub's
roadmap: a gantt chart of the project's milestones (from `start`, or the day the note was made,
to `target`, or `done_on` once done; end days included; dropped ones left out) and a flowchart of
the open tasks that wait on another open task, of any project, and the tasks they wait on,
grouped by milestone. With `--milestone` it draws that milestone's tasks, with `--change` the
change's `tasks`, each with the tasks they wait on; one of another project is refused. Arrows go
from a task to the one that waits on it (`blocked_by`); every task node is a link to its note,
styled by status.

Prints JSON (`markdown`, `tasks`, `edges`, `cycles`, `undated`), or with `--markdown` only the
Markdown to pipe into `synapsidian block set`. A cycle in `blocked_by` is drawn and reported, since
nothing can start until it is broken. Exit 2 = bad input or an unknown note.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from projects import fail, link_title

OPEN_TASK = {"todo", "doing", "waiting"}
# Status styles, in Excalidraw's palette like the map's (maps.py): blue under way, orange
# waiting, green done, grey dropped; `todo` keeps Mermaid's default look. The light fills set
# their own dark text: Obsidian colours a linked node's text as a link, unreadable on them in
# a dark theme.
CLASS_DEFS = {
    "doing": "fill:#d0ebff,stroke:#1971c2,color:#1e1e1e",
    "waiting": "fill:#fff4e6,stroke:#f08c00,color:#1e1e1e",
    "done": "fill:#ebfbee,stroke:#2f9e44,color:#868e96",
    "dropped": "fill:#f1f3f5,stroke:#868e96,color:#868e96,stroke-dasharray:4 3",
}
GANTT_TAG = {"active": "active, ", "done": "done, "}


def label(text: str) -> str:
    """Text inside a quoted Mermaid label: quotes, `#` and angle brackets as Mermaid's entity codes."""
    for char, code in (("#", "#35;"), ('"', "#quot;"), ("<", "#lt;"), (">", "#gt;")):
        text = text.replace(char, code)
    return " ".join(text.split())


def gantt_text(text: str) -> str:
    """A gantt task name: `:` ends it and `#` and `;` break the line, so they become plain dashes."""
    return " ".join(re.sub(r"[:#;]", " -", text).split())


def blockers(task: dict[str, Any]) -> list[str]:
    value = task.get("blocked_by")
    return [link_title(v) for v in (value if isinstance(value, list) else [value] if value else [])]


def find_cycles(edges: list[tuple[str, str]]) -> list[list[str]]:
    """Each cycle in the graph once, as the titles along it with the first repeated at the end."""
    after: dict[str, list[str]] = {}
    for start, end in edges:
        after.setdefault(start, []).append(end)
    cycles, seen_keys, done = [], set(), set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node) :]
            key = frozenset(cycle)
            if key not in seen_keys:
                seen_keys.add(key)
                cycles.append([*cycle, node])
            return
        if node in done:
            return
        for nxt in after.get(node, []):
            visit(nxt, [*path, node])
        done.add(node)

    for node in sorted(after):
        visit(node, [])
    return cycles


def flowchart(tasks: list[dict[str, Any]], by_title: dict[str, dict[str, Any]], groups: dict[str, str] | None = None
              ) -> tuple[list[str], list[tuple[str, str]], list[list[str]]]:  # fmt: skip
    """Mermaid lines for `tasks` and the tasks they wait on, edges as (blocker, task) titles."""
    shown: dict[str, dict[str, Any]] = {t["title"].casefold(): t for t in tasks}
    edges: list[tuple[str, str]] = []
    for task in tasks:
        for name in blockers(task):
            blocker = by_title.get(name.casefold())
            if blocker is None or blocker.get("type") != "task":
                continue  # a link to a note that isn't a task, or to nothing, isn't an order
            shown.setdefault(blocker["title"].casefold(), blocker)
            if (blocker["title"], task["title"]) not in edges:
                edges.append((blocker["title"], task["title"]))
    ids = {key: f"n{i}" for i, key in enumerate(sorted(shown, key=lambda k: task_order(shown[k])), 1)}
    lines = ["flowchart LR"]

    def node(key: str) -> str:
        return f'    {ids[key]}["{label(shown[key]["title"])}"]'

    grouped: dict[str, list[str]] = {}
    for key in shown:
        grouped.setdefault((groups or {}).get(key) or "", []).append(key)
    for key in sorted(grouped.get("", []), key=ids.get):
        lines.append(node(key))
    for i, group in enumerate(sorted(g for g in grouped if g), 1):
        lines.append(f'    subgraph g{i}["{label(group)}"]')
        lines += [f"    {node(key)}" for key in sorted(grouped[group], key=ids.get)]
        lines.append("    end")
    for start, end in edges:
        lines.append(f"    {ids[start.casefold()]} --> {ids[end.casefold()]}")
    by_status: dict[str, list[str]] = {}
    for key, task in shown.items():
        if task.get("status") in CLASS_DEFS:
            by_status.setdefault(task["status"], []).append(ids[key])
    for status, members in sorted(by_status.items()):
        lines += [f"    classDef {status} {CLASS_DEFS[status]}", f"    class {','.join(sorted(members))} {status}"]
    lines.append(f"    class {','.join(sorted(ids.values(), key=lambda i: int(i[1:])))} internal-link")
    return lines, edges, find_cycles(edges)


def task_order(task: dict[str, Any]) -> tuple[int, str]:
    number = re.match(r"T(\d+)\b", task["title"])
    return (int(number.group(1)) if number else 10**9, task["title"])


def fenced(lines: list[str]) -> str:
    return "```mermaid\n" + "\n".join(lines) + "\n```"


def gantt(milestones: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    """A gantt chart of the dated milestones, and the titles of the open ones with no `target`.
    A done milestone ends on its `done_on`, with or without a target."""
    rows, undated = [], []
    for m in sorted(milestones, key=lambda m: (str(m.get("done_on") or m.get("target") or ""), m["title"])):
        start, end = str(m.get("start") or m.get("created") or ""), str(m.get("done_on") or m.get("target") or "")
        if not end or not start:
            undated.append(m["title"])
            continue
        end = max(start, end)  # a target before the start would draw nothing
        tag = GANTT_TAG.get(m.get("status"), "")
        rows.append(f"    {gantt_text(m['title'])} :{tag}m{len(rows) + 1}, {start}, {end}")
    if not rows:
        return None, undated
    # The end day is part of the bar: a milestone due on the day it starts still shows.
    header = ["gantt", "    dateFormat YYYY-MM-DD", "    inclusiveEndDates", "    section Milestones"]
    return fenced([*header, *rows]), undated


def cycle_lines(cycles: list[list[str]]) -> list[str]:
    return [f"- ⚠ Waiting on each other, nothing here can start: {' → '.join(f'[[{t}]]' for t in c)}" for c in cycles]


def roadmap(notes: list[dict[str, Any]], hub: dict[str, Any], by_title: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mine = [n for n in notes if link_title(n.get("project")).casefold() == hub["title"].casefold()]
    milestones = [n for n in mine if n.get("type") == "milestone" and n.get("status") != "dropped"]
    open_tasks = [n for n in mine if n.get("type") == "task" and n.get("status") in OPEN_TASK]
    # A blocker may be another project's task: it is drawn too, outside the milestone groups.
    open_titles = {n["title"].casefold() for n in notes if n.get("type") == "task" and n.get("status") in OPEN_TASK}

    def open_blockers(task: dict[str, Any]) -> set[str]:
        return {name.casefold() for name in blockers(task)} & open_titles

    # Open tasks that still wait on an open task, and the open tasks they wait on.
    waited_on = {name for t in open_tasks for name in open_blockers(t)}
    linked = [t for t in open_tasks if open_blockers(t) or t["title"].casefold() in waited_on]
    chart, undated = gantt(milestones)
    parts = [chart] if chart else []
    parts += [f"- No target date yet: {', '.join(f'[[{t}]]' for t in undated)}"] if undated else []
    edges, cycles = [], []
    if linked:
        groups = {t["title"].casefold(): link_title(t.get("milestone")) for t in mine if t.get("milestone")}
        lines, edges, cycles = flowchart(linked, by_title, groups)
        parts += [fenced(lines), *cycle_lines(cycles)]
    if not parts:
        parts = ["No milestones or tasks waiting on each other yet."]
    return {"markdown": "\n\n".join(parts), "tasks": len(linked), "edges": len(edges), "cycles": cycles,
            "milestones": len(milestones), "undated": undated}  # fmt: skip


def task_flow(tasks: list[dict[str, Any]], by_title: dict[str, dict[str, Any]], empty: str) -> dict[str, Any]:
    if not tasks:
        return {"markdown": empty, "tasks": 0, "edges": 0, "cycles": []}
    lines, edges, cycles = flowchart(tasks, by_title)
    markdown = "\n\n".join([fenced(lines), *cycle_lines(cycles)])
    return {"markdown": markdown, "tasks": len(tasks), "edges": len(edges), "cycles": cycles}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="the project's hub title")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--milestone", help="a milestone's title: its tasks in order")
    which.add_argument("--change", help="a change's title: its tasks in order")
    parser.add_argument("--markdown", action="store_true", help="print only the Markdown for `synapsidian block set`")
    args = parser.parse_args()
    try:
        notes = json.loads(sys.stdin.read() or "{}").get("notes") or []
    except (json.JSONDecodeError, AttributeError) as exc:
        fail(2, f"stdin is not `synapsidian query notes` JSON: {exc}")
    by_title = {n["title"].casefold(): n for n in notes if n.get("title")}

    def find(title: str, kind: str) -> dict[str, Any]:
        note = by_title.get(title.casefold())
        if note is None or note.get("type") != kind:
            fail(2, f"no {kind} note titled {title!r} in the query (pass `synapsidian query notes --limit 100000`)")
        owner = link_title(note.get("project"))
        if kind != "project" and owner.casefold() != hub["title"].casefold():
            fail(2, f"{kind} {title!r} belongs to {owner or 'no project'!r}, not {hub['title']!r}")
        return note

    hub = find(args.project, "project")
    if args.milestone:
        milestone = find(args.milestone, "milestone")
        tasks = [n for n in notes if n.get("type") == "task" and link_title(n.get("milestone")).casefold()
                 == milestone["title"].casefold()]  # fmt: skip
        result = task_flow(tasks, by_title, "No tasks in this milestone yet.")
    elif args.change:
        change = find(args.change, "change")
        linked = [by_title.get(link_title(v).casefold()) for v in change.get("tasks") or []]
        tasks = list({t["title"]: t for t in linked if t and t.get("type") == "task"}.values())  # links may repeat
        result = task_flow(tasks, by_title, "No tasks linked to this change yet.")
    else:
        result = roadmap(notes, hub, by_title)
    if args.markdown:
        print(result["markdown"])
        return
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
