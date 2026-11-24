#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate or refresh a project's Excalidraw mind map (D103, D108).

  synapsidian query notes --limit 100000 | maps.py --project "Web app" [--max-leaves 10]

Reads `synapsidian query notes` JSON on stdin, finds the project's hub and the notes that link to it,
and writes `Projects/<Project>/Maps/<Project> map.excalidraw.md` next to the hub: the hub in
the middle, one branch per kind (open milestones, open tasks, decisions, specs in force, open changes, bugs under
investigation, draft postmortems, architecture overviews, the hub's open questions, research,
workflows, notes, thinking), one node per note as a `[[link]]`, coloured by its status. A branch
longer than `--max-leaves` (0: no limit) ends in a `+N more` link to the hub's list of them.

The file is the Excalidraw plugin's own format, with plain JSON (setup turns compression off).
Every element the map makes carries `customData.synapsidian`, a stable key, so a refresh:
- keeps where the user moved, resized or recoloured a generated node, and updates only its text
  and, unless the user recoloured it, its status colour;
- keeps a node in place when its note is renamed or its open question reworded;
- puts a new node under its siblings, or next to its branch where the branch now is, and then
  down past any box it would cover, generated or the user's own; nothing already drawn moves;
- removes the generated nodes of notes that left the map (closed, archived, superseded, retired),
  and unbinds the user's arrows from them;
- never touches an element without that key: everything the user drew stays.
Arrows between generated nodes are redrawn from where their nodes are now.

Prints JSON: the file, whether it was created, and the keys added, updated and removed.
Exit 2 = bad input or a drawing it can't read (compressed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from projects import fail, link_title

OPEN_TASK = {"todo", "doing", "waiting"}
GONE_DECISION = {"superseded", "rejected", "deprecated"}
MAX_LEAVES = 10
# Where a branch's `+N more` link points in the hub: the list that holds all of them.
MORE_TARGET = {"Open tasks": "Board", "Open questions": "Open questions"}
DEFAULT_STROKE = "#1e1e1e"
# A leaf's text colour by (type, status), from Excalidraw's palette: blue under way, orange
# waiting, grey not settled yet, red an open bug. Any other status keeps the default.
STATUS_COLOR = {
    ("task", "doing"): "#1971c2",
    ("task", "waiting"): "#f08c00",
    ("milestone", "active"): "#1971c2",
    ("change", "doing"): "#1971c2",
    ("change", "proposed"): "#868e96",
    ("decision", "proposed"): "#868e96",
    ("spec", "draft"): "#868e96",
    ("debug", "investigating"): "#e03131",
}
RENAME_SIMILARITY = 0.6  # how alike a leaf's old and new text must be to count as one renamed node
TITLE_ID = re.compile(r"(T\d+|\d{4}-\d{2}-\d{2}) ")  # a task id or a date a rename never changes
LABEL_CHARS = 48
FONT = {0: 32, 1: 24, 2: 18}
CHAR_WIDTH = 0.55  # Virgil, the drawing font, averages about this many font sizes per character
LINE_HEIGHT = 1.25
ROW = 38  # vertical space per leaf
BRANCH_GAP = 160
LEAF_GAP = 70
BLOCK_GAP = 40
PAD = 8  # the least space a new node keeps from a box already drawn
PASS_THROUGH = {"arrow", "line", "frame", "magicframe"}  # never boxes a new node has to avoid
HUB_STYLE = {"backgroundColor": "#ffec99", "fillStyle": "solid"}
BRANCH_STYLE = {"backgroundColor": "#a5d8ff", "fillStyle": "solid", "roundness": {"type": 3}}

HEADER = """---

excalidraw-plugin: parsed
tags: [excalidraw]

---
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress \
Drawing data with the command palette: 'Decompress current Excalidraw file'. For more info check in \
plugin settings under 'Saving'

# Excalidraw Data

"""
APP_STATE = {"theme": "light", "viewBackgroundColor": "#ffffff", "currentItemFontFamily": 1, "gridSize": 0}


def shorten(text: str, limit: int = LABEL_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def wiki(title: str, label: str | None = None) -> str:
    """A link the drawing shows as its label: `[[title]]`, or `[[title|label]]` when they differ."""
    label = shorten(label or title)
    return f"[[{title}]]" if label == title else f"[[{title}|{label}]]"


def shown(text: str) -> str:
    """What a node's text looks like on the canvas: a link shows its label."""
    return re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), text)


# --- what goes on the map -----------------------------------------------------


@dataclass
class Node:
    key: str
    text: str
    level: int
    parent: str | None = None
    color: str | None = None  # a leaf's status colour


Leaf = tuple[str, str, str | None]  # key, text, status colour


def open_questions(hub: Path) -> list[str]:
    """Top-level bullets of the hub's `## Open questions`; a "None ..." line means there are none."""
    try:
        text = hub.read_text(encoding="utf-8")
    except OSError:
        return []
    section = re.search(r"^## Open questions[ \t]*\n(.*?)(?=^#{1,2} |\Z)", text, re.M | re.S)
    if not section:
        return []
    bullets = [line[2:].strip() for line in section.group(1).splitlines() if line.startswith(("- ", "* "))]
    return [b for b in bullets if b and not re.match(r"(none|tbd)\b", b, re.I)]


def branches(notes: list[dict[str, Any]], hub: dict[str, Any]) -> list[tuple[str, list[Leaf]]]:
    """(branch name, leaves) in map order, empty branches left out."""
    project = hub["title"].casefold()
    mine = [n for n in notes if link_title(n.get("project")).casefold() == project]

    def of(kind: str) -> list[dict[str, Any]]:
        return [n for n in mine if n.get("type") == kind]

    def task_order(n: dict[str, Any]) -> tuple[int, int]:
        number = re.match(r"T(\d+)$", str(n.get("id") or ""))
        return (["doing", "waiting", "todo"].index(n.get("status")), int(number.group(1)) if number else 0)

    tasks = sorted((n for n in of("task") if n.get("status") in OPEN_TASK), key=task_order)
    milestones = sorted(
        (n for n in of("milestone") if n.get("status") in {"planned", "active"}),
        key=lambda n: (str(n.get("target") or "9999"), n["title"]),
    )
    decisions = sorted(
        (n for n in of("decision") if n.get("status") not in GONE_DECISION), key=lambda n: n["title"], reverse=True
    )
    changes = sorted((n for n in of("change") if n.get("status") not in {"done", "dropped"}), key=lambda n: n["title"])
    bugs = sorted((n for n in of("debug") if n.get("status") == "investigating"), key=lambda n: n["title"])
    incidents = sorted((n for n in of("incident") if n.get("status") == "draft"), key=lambda n: n["title"])

    def undated(n: dict[str, Any]) -> str:
        return re.sub(r"^\d{4}-\d{2}-\d{2} ", "", n["title"])

    def decision_label(n: dict[str, Any]) -> str:
        return f"#{n['number']} {undated(n)}" if isinstance(n.get("number"), int) else undated(n)

    def notes_of(found: list[dict[str, Any]], label=lambda n: n["title"]) -> list[Leaf]:
        return [(f"note:{n['title']}", wiki(n["title"], label(n)), STATUS_COLOR.get((n.get("type"), n.get("status"))))
                for n in found]  # fmt: skip

    questions = [(f"question:{hashlib.sha1(q.encode()).hexdigest()[:10]}", shorten(q, 60), None)
                 for q in open_questions(Path(hub["path"]))]  # fmt: skip
    by_title = lambda kind: sorted(of(kind), key=lambda n: n["title"])  # noqa: E731
    overviews = [n for n in by_title("architecture") if n.get("kind") == "overview"]
    specs = [n for n in by_title("spec") if n.get("status") != "retired"]

    def milestone_label(n: dict[str, Any]) -> str:
        return f"{n['title']} ({n['target']})" if n.get("target") else n["title"]

    found = [
        ("Milestones", notes_of(milestones, milestone_label)),
        ("Open tasks", notes_of(tasks)),
        ("Decisions", notes_of(decisions, decision_label)),
        ("Specs", notes_of(specs)),
        ("Changes", notes_of(changes)),
        ("Open bugs", notes_of(bugs, undated)),
        ("Draft postmortems", notes_of(incidents, undated)),
        ("Architecture", notes_of(overviews)),
        ("Open questions", questions),
        ("Research", notes_of(by_title("research"))),
        ("Workflows", notes_of(by_title("howto"))),
        ("Notes", notes_of(by_title("note"))),
        ("Thinking", notes_of(by_title("thinking"), undated)),
    ]
    return [(name, leaves) for name, leaves in found if leaves]


def wanted_nodes(notes: list[dict[str, Any]], hub: dict[str, Any], max_leaves: int = MAX_LEAVES) -> list[Node]:
    nodes = [Node("hub", wiki(hub["title"]), 0)]
    for name, leaves in branches(notes, hub):
        key = f"branch:{name}"
        nodes.append(Node(key, name, 1, "hub"))
        drawn = leaves[:max_leaves] if max_leaves else leaves
        nodes += [Node(k, text, 2, key, color) for k, text, color in drawn]
        if len(leaves) > len(drawn):
            target = f"{hub['title']}#{MORE_TARGET.get(name, 'Project notes')}"
            nodes.append(Node(f"more:{name}", wiki(target, f"+{len(leaves) - len(drawn)} more"), 2, key))
    return nodes


# --- geometry -----------------------------------------------------------------


def text_size(text: str, level: int) -> tuple[float, float]:
    size = FONT[level]
    return round(max(len(shown(text)), 1) * size * CHAR_WIDTH, 2), round(size * LINE_HEIGHT, 2)


def box_size(text: str, level: int) -> tuple[float, float]:
    w, h = text_size(text, level)
    return {0: (w + 80, h + 50), 1: (w + 40, h + 24), 2: (w, h)}[level]


def layout(nodes: list[Node]) -> dict[str, tuple[float, float]]:
    """Top-left corner of each node's box: branches on both sides of the hub, leaves beyond them."""
    hub_w, hub_h = box_size(nodes[0].text, 0)
    pos = {"hub": (-hub_w / 2, -hub_h / 2)}
    children: dict[str, list[Node]] = {}
    for n in nodes[1:]:
        children.setdefault(n.parent or "", []).append(n)
    blocks = [(b, max(box_size(b.text, 1)[1], len(children.get(b.key, [])) * ROW)) for b in children.get("hub", [])]
    sides: dict[int, list[tuple[Node, float]]] = {1: [], -1: []}
    for block in blocks:  # the shorter side takes the next branch
        side = 1 if sum(h for _, h in sides[1]) <= sum(h for _, h in sides[-1]) else -1
        sides[side].append(block)
    for side, column in sides.items():
        y = -(sum(h for _, h in column) + BLOCK_GAP * max(len(column) - 1, 0)) / 2
        for branch, height in column:
            bw, bh = box_size(branch.text, 1)
            bx = hub_w / 2 + BRANCH_GAP if side == 1 else -hub_w / 2 - BRANCH_GAP - bw
            pos[branch.key] = (bx, y + (height - bh) / 2)
            leaves = children.get(branch.key, [])
            ly = y + (height - len(leaves) * ROW) / 2
            for leaf in leaves:
                lw, lh = box_size(leaf.text, 2)
                lx = bx + bw + LEAF_GAP if side == 1 else bx - LEAF_GAP - lw
                pos[leaf.key] = (lx, ly + (ROW - lh) / 2)
                ly += ROW
            y += height + BLOCK_GAP
    return pos


def border_point(box: tuple[float, float, float, float], toward: tuple[float, float]) -> tuple[float, float]:
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = toward[0] - cx, toward[1] - cy
    if dx == dy == 0:
        return cx, cy
    t = min((w / 2) / abs(dx) if dx else math.inf, (h / 2) / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t


# --- elements -----------------------------------------------------------------


ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def element_id(key: str) -> str:
    """Eight characters, like the plugin's own ids; it replaces ids of any other shape when it saves."""
    n = int(hashlib.sha1(key.encode()).hexdigest(), 16)
    out = ""
    for _ in range(8):
        n, r = divmod(n, len(ID_ALPHABET))
        out += ID_ALPHABET[r]
    return out


def raw(e: dict[str, Any]) -> str:
    """A text element's source text: the plugin keeps a link in `rawText` and shows its label in `text`."""
    return e.get("rawText") or e.get("text") or ""


def seed(key: str) -> int:
    return int(hashlib.sha1(("seed" + key).encode()).hexdigest()[:8], 16) % 2_000_000_000


def base(key: str, kind: str, x: float, y: float, w: float, h: float, now: int) -> dict[str, Any]:
    return {
        "id": element_id(key),
        "type": kind,
        "x": round(x, 2),
        "y": round(y, 2),
        "width": round(w, 2),
        "height": round(h, 2),
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2 if kind != "text" else 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "roundness": None,
        "seed": seed(key),
        "version": 1,
        "versionNonce": seed("nonce" + key),
        "updated": now,
        "isDeleted": False,
        "groupIds": [],
        "frameId": None,
        "boundElements": [],
        "link": None,
        "locked": False,
        "customData": {"synapsidian": key},
    }


def text_element(key: str, text: str, level: int, x: float, y: float, container: str | None, now: int) -> dict:
    w, h = text_size(text, level)
    return base(key, "text", x, y, w, h, now) | {
        "text": text,
        "rawText": text,
        "originalText": text,
        "fontSize": FONT[level],
        "fontFamily": 1,
        "textAlign": "center" if container else "left",
        "verticalAlign": "middle" if container else "top",
        "containerId": container,
        "lineHeight": LINE_HEIGHT,
        "autoResize": True,
    }


def arrow_element(key: str, start: dict, end: dict, now: int) -> dict[str, Any]:
    return base(key, "arrow", 0, 0, 0, 0, now) | {
        "points": [[0, 0], [0, 0]],
        "lastCommittedPoint": None,
        "startBinding": {"elementId": start["id"], "mode": "orbit", "fixedPoint": [0.5001, 0.5001]},
        "endBinding": {"elementId": end["id"], "mode": "orbit", "fixedPoint": [0.5001, 0.5001]},
        "startArrowhead": None,
        "endArrowhead": "arrow" if end["type"] == "text" else None,
        "elbowed": False,
        "strokeWidth": 1,
    }


def box(e: dict[str, Any]) -> tuple[float, float, float, float]:
    return e["x"], e["y"], e["width"], e["height"]


def route(arrow: dict[str, Any], start: dict[str, Any], end: dict[str, Any]) -> None:
    """Point `arrow` from the edge of `start` to the edge of `end`, where they are now."""
    sb, eb = box(start), box(end)
    s = border_point(sb, (eb[0] + eb[2] / 2, eb[1] + eb[3] / 2))
    e = border_point(eb, (sb[0] + sb[2] / 2, sb[1] + sb[3] / 2))
    length = math.dist(s, e) or 1
    gap = min(8, length / 4)
    ux, uy = (e[0] - s[0]) / length, (e[1] - s[1]) / length
    sx, sy, ex, ey = s[0] + ux * gap, s[1] + uy * gap, e[0] - ux * gap, e[1] - uy * gap
    arrow.update({
        "x": round(sx, 2), "y": round(sy, 2),
        "width": round(abs(ex - sx), 2), "height": round(abs(ey - sy), 2),
        "points": [[0, 0], [round(ex - sx, 2), round(ey - sy, 2)]],
    })  # fmt: skip
    arrow["startBinding"] = (arrow.get("startBinding") or {}) | {"elementId": start["id"]}
    arrow["endBinding"] = (arrow.get("endBinding") or {}) | {"elementId": end["id"]}


# --- the file -----------------------------------------------------------------


@dataclass
class Drawing:
    head: str  # everything before `## Text Elements`
    texts: dict[str, str]  # element id → its text in the Text Elements section
    middle: str  # from the end of that section to the JSON (other sections, `%%`, `## Drawing`)
    scene: dict[str, Any]
    tail: str  # after the JSON's closing fence


JSON_BLOCK = re.compile(r"^```(json|compressed-json)\n(.*?)\n```", re.M | re.S)
TEXT_SECTION = re.compile(r"^## Text Elements\n(.*?)(?=^## |^%%)", re.M | re.S)
TEXT_ENTRY = re.compile(r"\s*(.*?) \^([\w-]+)\n", re.S)


def read_drawing(path: Path) -> Drawing:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    # The scene is the JSON under `## Drawing`, which Excalidraw puts last; a ```json snippet the
    # user wrote above it is not the drawing.
    drawing = text.find("\n## Drawing\n")
    blocks = list(JSON_BLOCK.finditer(text, drawing if drawing >= 0 else 0))
    block = blocks[0] if drawing >= 0 and blocks else blocks[-1] if blocks else None
    if not block:
        fail(2, f"{path.name}: no drawing data found")
    if block.group(1) == "compressed-json":
        fail(2, f"{path.name} is compressed; turn off Excalidraw's 'Compress Excalidraw JSON' and save it once")
    try:
        scene = json.loads(block.group(2))
    except json.JSONDecodeError as exc:
        fail(2, f"{path.name}: drawing data is not JSON: {exc}")
    before = text[: block.start()]
    section = TEXT_SECTION.search(before)
    if section:
        texts = {m.group(2): m.group(1) for m in TEXT_ENTRY.finditer(section.group(1))}
        head, middle = before[: section.start()], before[section.end() :]
    else:
        cut = before.find("%%\n## Drawing")
        cut = cut if cut >= 0 else len(before)
        texts, head, middle = {}, before[:cut], before[cut:]
    return Drawing(head, texts, middle, scene, text[block.end() :])


def new_drawing() -> Drawing:
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin",
        "elements": [],
        "appState": APP_STATE,
        "files": {},
    }
    return Drawing(HEADER, {}, "%%\n## Drawing\n", scene, "\n%%\n")


def render(d: Drawing) -> str:
    entries = []
    for e in d.scene["elements"]:
        if e.get("type") == "text" and not e.get("isDeleted"):
            # The section wins over the JSON when the plugin loads, so keep the user's own wording there.
            text = raw(e) if is_ours(e) else d.texts.get(e["id"], raw(e))
            entries.append(f"{text} ^{e['id']}\n\n")
    body = json.dumps(d.scene, ensure_ascii=False, indent="\t")
    return f"{d.head}## Text Elements\n{''.join(entries)}\n{d.middle}```json\n{body}\n```{d.tail}"


def is_ours(e: dict[str, Any]) -> bool:
    return isinstance(e.get("customData"), dict) and "synapsidian" in e["customData"]


# --- merge --------------------------------------------------------------------


def paint(e: dict[str, Any], color: str | None) -> bool:
    """Give a leaf its status colour, unless the user recoloured it: `customData.color` is the
    colour the map gave it last. True when the colour changed."""
    color = color or DEFAULT_STROKE
    given = e["customData"].get("color", DEFAULT_STROKE)
    if e.get("strokeColor", DEFAULT_STROKE) != given or given == color:
        return False
    e["strokeColor"] = color
    if color == DEFAULT_STROKE:
        e["customData"].pop("color", None)
    else:
        e["customData"]["color"] = color
    return True


def follow_renames(ours: dict[str, dict[str, Any]], nodes: list[Node], titles: AbstractSet[str]) -> None:
    """Re-key the leaf of a renamed note or a reworded open question, so it keeps its element and
    where the user put it: a wanted leaf with no element takes the most similar leaf of the same
    branch that is no longer wanted. A task id or date that starts a title must match, and a note
    still in the vault under its old title (`titles`, casefolded) left the map rather than being
    renamed: a retired spec next to its successor stays two notes."""
    parent_of: dict[str, str] = {}
    for key in ours:
        if key.startswith("edge:"):
            parent, child = key.removeprefix("edge:").split(">", 1)
            parent_of[child] = parent
    wanted = {n.key for n in nodes}
    gone = [k for k in ours if k not in wanted and k in parent_of
            and not (k.startswith("note:") and k.removeprefix("note:").casefold() in titles)]  # fmt: skip

    def kind(key: str) -> str:
        return key.split(":", 1)[0]

    def title_id(key: str) -> str | None:
        found = TITLE_ID.match(key.removeprefix("note:"))
        return found.group(1) if found else None

    pairs = []
    for node in nodes:
        if node.level != 2 or node.key in ours or kind(node.key) not in {"note", "question"}:
            continue
        for old in gone:
            if parent_of[old] != node.parent or kind(old) != kind(node.key) or title_id(old) != title_id(node.key):
                continue
            ratio = SequenceMatcher(None, shown(raw(ours[old])), shown(node.text)).ratio()
            if ratio >= RENAME_SIMILARITY:
                pairs.append((ratio, old, node))
    for _, old, node in sorted(pairs, key=lambda p: -p[0]):
        if old not in ours or node.key in ours:
            continue
        for was, new in ((old, node.key), (f"edge:{node.parent}>{old}", f"edge:{node.parent}>{node.key}")):
            if was in ours:
                ours[new] = ours.pop(was)
                ours[new]["customData"]["synapsidian"] = new


def merge(d: Drawing, nodes: list[Node], now: int, titles: AbstractSet[str] = frozenset()) -> dict[str, list[str]]:
    elements: list[dict[str, Any]] = d.scene.setdefault("elements", [])
    ours = {e["customData"]["synapsidian"]: e for e in elements if is_ours(e) and not e.get("isDeleted")}
    snapshot = {e["id"]: json.dumps(e, sort_keys=True) for e in ours.values()}
    follow_renames(ours, nodes, titles)
    before = {k: snapshot[e["id"]] for k, e in ours.items()}
    known = set(ours)
    planned = layout(nodes)
    report: dict[str, list[str]] = {"added": [], "updated": [], "removed": []}

    shapes: dict[str, dict[str, Any]] = {}  # node key → the element arrows attach to
    wanted: set[str] = set()
    for node in nodes:
        w, h = box_size(node.text, node.level)
        shape = ours.get(node.key)
        if shape is None:
            x, y = place(node, nodes, planned, shapes, known, elements)
            kind = {0: "ellipse", 1: "rectangle", 2: "text"}[node.level]
            if kind == "text":
                shape = text_element(node.key, node.text, 2, x, y, None, now)
                paint(shape, node.color)
            else:
                shape = base(node.key, kind, x, y, w, h, now) | (HUB_STYLE if node.level == 0 else BRANCH_STYLE)
            elements.append(shape)
            ours[node.key] = shape
            report["added"].append(node.key)
        elif shape["type"] == "text":
            renamed = raw(shape) != node.text
            if renamed:
                tw, th = text_size(node.text, 2)
                shape.update(text=node.text, rawText=node.text, originalText=node.text, width=tw, height=th)
            if paint(shape, node.color) or renamed:
                report["updated"].append(node.key)
        else:
            label = ours.get(f"{node.key}/text")
            if label is not None and raw(label) != node.text:  # wider text, wider box
                shape.update(width=max(shape["width"], w), height=max(shape["height"], h))
                report["updated"].append(node.key)
        wanted.add(node.key)
        shapes[node.key] = shape
        if node.level < 2:
            label_key = f"{node.key}/text"
            label = ours.get(label_key)
            # The plugin measures and moves a container's text itself; touch it only when the text changes.
            if label is None or raw(label) != node.text:
                tw, th = text_size(node.text, node.level)
                cx, cy = shape["x"] + shape["width"] / 2, shape["y"] + shape["height"] / 2
                if label is None:
                    label = text_element(label_key, node.text, node.level, 0, 0, shape["id"], now)
                    elements.append(label)
                    ours[label_key] = label
                label.update(text=node.text, rawText=node.text, originalText=node.text, width=tw, height=th,
                             x=round(cx - tw / 2, 2), y=round(cy - th / 2, 2))  # fmt: skip
            label["containerId"] = shape["id"]
            wanted.add(label_key)

    for node in nodes:
        if node.parent is None:
            continue
        key = f"edge:{node.parent}>{node.key}"
        arrow = ours.get(key)
        if arrow is None:
            arrow = arrow_element(key, shapes[node.parent], shapes[node.key], now)
            elements.insert(0, arrow)  # under the nodes
            ours[key] = arrow
        route(arrow, shapes[node.parent], shapes[node.key])
        wanted.add(key)

    gone = {e["id"] for k, e in ours.items() if k not in wanted}
    report["removed"] = sorted(k for k in ours if k not in wanted and "/" not in k and not k.startswith("edge:"))
    elements[:] = [e for e in elements if e["id"] not in gone]
    for e in elements:  # the user's arrows that pointed at a removed node now end where they are
        for end in ("startBinding", "endBinding"):
            if isinstance(e.get(end), dict) and e[end].get("elementId") in gone:
                e[end] = None
    bound: dict[str, list[dict[str, str]]] = {}
    for e in elements:
        if e["type"] == "text" and e.get("containerId"):
            bound.setdefault(e["containerId"], []).append({"type": "text", "id": e["id"]})
        if e["type"] == "arrow":
            for end in ("startBinding", "endBinding"):
                if isinstance(e.get(end), dict):
                    bound.setdefault(e[end]["elementId"], []).append({"type": "arrow", "id": e["id"]})
    for e in elements:
        refs = bound.get(e["id"], [])
        unique = list({(r["type"], r["id"]): r for r in refs}.values())
        if unique or e.get("boundElements"):
            e["boundElements"] = unique

    for key, e in ours.items():  # Excalidraw syncs by version: any change to an element bumps it
        if key in before and key in wanted and json.dumps(e, sort_keys=True) != before[key]:
            e["version"] = int(e.get("version", 1)) + 1
            e["updated"] = now
    return report


def taken(elements: list[dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    """The boxes a new node must not cover: every shape and free text on the canvas, the user's
    included. Arrows and lines cross everything, a frame holds other elements, and a container's
    text sits inside its container's box."""
    return [box(e) for e in elements
            if not e.get("isDeleted") and e.get("type") not in PASS_THROUGH and not e.get("containerId")
            and all(isinstance(e.get(k), int | float) for k in ("x", "y", "width", "height"))]  # fmt: skip


def clear_below(x: float, y: float, w: float, h: float, boxes: list[tuple[float, float, float, float]]) -> float:
    """The first `y` at or below the given one where a `w` × `h` box at `x` keeps PAD clear of
    every box. One pass by top edge is enough: a box passed or skipped can't be hit again, since
    `y` only grows."""
    for bx, by, bw, bh in sorted(boxes, key=lambda b: b[1]):
        if bx < x + w + PAD and x < bx + bw + PAD and by < y + h + PAD and y < by + bh + PAD:
            y = by + bh + PAD
    return y


def place(
    node: Node,
    nodes: list[Node],
    planned: dict[str, tuple[float, float]],
    shapes: dict[str, dict[str, Any]],
    known: set[str],
    elements: list[dict[str, Any]],
) -> tuple[float, float]:
    """Where a new node goes. Under its lowest sibling when the drawing already had one of its
    siblings (`known`: the keys drawn before this run), right-aligned on the hub's left side; else
    where the layout puts it, shifted by however far its parent moved. Then down past any box it
    would cover, so a branch that grows never runs into the next one or into the user's drawing."""
    w, h = box_size(node.text, node.level)
    siblings = [n.key for n in nodes if n.parent == node.parent and n.key in shapes and n.key != node.key]
    parent = shapes.get(node.parent or "")
    if parent and any(k in known for k in siblings):
        lowest = max((shapes[k] for k in siblings), key=lambda e: e["y"] + e["height"])
        left = lowest["x"] + lowest["width"] / 2 < parent["x"] + parent["width"] / 2
        x = lowest["x"] + lowest["width"] - w if left else lowest["x"]
        y = lowest["y"] + max(ROW, lowest["height"] + PAD)
    else:
        x, y = planned[node.key]
        if parent:
            px, py = planned[node.parent or ""]
            x += parent["x"] - px
            y += parent["y"] - py
    return x, clear_below(x, y, w, h, taken(elements))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="the project's hub title")
    parser.add_argument("--max-leaves", type=int, default=MAX_LEAVES, help="leaves per branch, 0 for all")
    parser.add_argument("--now", type=int, help=argparse.SUPPRESS)  # tests: a fixed `updated` time
    args = parser.parse_args()
    try:
        notes = json.loads(sys.stdin.read() or "{}").get("notes") or []
    except (json.JSONDecodeError, AttributeError) as exc:
        fail(2, f"stdin is not `synapsidian query notes` JSON: {exc}")
    if args.max_leaves < 0:
        fail(2, "--max-leaves must be 0 (no limit) or more")
    hub = next((n for n in notes if n.get("type") == "project" and n["title"].casefold() == args.project.casefold()),
               None)  # fmt: skip
    if hub is None:
        fail(2, f"no project note titled {args.project!r} in the query (pass `synapsidian query notes --limit 100000`)")
    path = Path(hub["path"]).parent / "Maps" / f"{hub['title']} map.excalidraw.md"
    created = not path.exists()
    drawing = new_drawing() if created else read_drawing(path)
    titles = {str(n["title"]).casefold() for n in notes if n.get("title")}
    report = merge(drawing, wanted_nodes(notes, hub, args.max_leaves), args.now or int(time.time() * 1000), titles)
    text = render(drawing)
    changed = created or text != path.read_text(encoding="utf-8")
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    rel = str(Path(hub["rel"]).parent / "Maps" / path.name)
    print(json.dumps({"ok": True, "rel": rel, "link": f"[[{path.name.removesuffix('.md')}]]", "created": created,
                      "changed": changed, **report}, ensure_ascii=False))  # fmt: skip


if __name__ == "__main__":
    main()
