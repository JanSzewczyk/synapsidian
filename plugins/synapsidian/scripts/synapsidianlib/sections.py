"""`## ` sections of a note body: find them, fill an empty one, add to one (note.py fill, block.py set)."""

from __future__ import annotations

import re
from typing import Literal

FENCE = re.compile(r"^(`{3,}|~{3,})")
SECTION_END = re.compile(r"^#{1,2} ")

FillStatus = Literal["filled", "added", "kept"]


def sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """(title, heading line, end line) of each `## ` section; headings inside code fences don't count."""
    found: list[tuple[str, int, int]] = []
    fence: str | None = None
    for i, line in enumerate(lines):
        if match := FENCE.match(line):
            marker = match.group(1)
            if fence is None:
                fence = marker
            # CommonMark: only a run of the same character, at least as long, closes a fence,
            # so a ``` line inside a ```` block is content.
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not line[len(marker) :].strip():
                fence = None
            continue
        if fence is None and SECTION_END.match(line):
            if found and found[-1][2] == -1:
                found[-1] = (found[-1][0], found[-1][1], i)
            found.append((line[3:].strip(), i, -1) if line.startswith("## ") else ("", i, -1))
    if found and found[-1][2] == -1:
        found[-1] = (found[-1][0], found[-1][1], len(lines))
    return [s for s in found if s[0]]


def _lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def _find(found: list[tuple[str, int, int]], title: str | None) -> tuple[str, int, int] | None:
    key = (title or "").strip().casefold()
    return next((s for s in found if key and s[0].casefold() == key), None)


def _add(lines: list[str], found: list[tuple[str, int, int]], title: str, inner: str, before: str | None) -> str:
    """A new `## title` section holding `inner`, before the `before` section, else at the end."""
    block = [f"## {title.strip()}\n", inner]
    if anchor := _find(found, before):
        return "".join([*lines[: anchor[1]], *block, "\n", *lines[anchor[1] :]])
    head = "".join(lines).rstrip("\n")
    return (f"{head}\n\n" if head else "") + "".join(block)


def fill_section(text: str, title: str, content: str, before: str | None = None) -> tuple[str, FillStatus]:
    """Put `content` under `## title` only if that section is empty or missing; never touch other text."""
    lines = _lines(text)
    inner = content.strip("\n") + "\n"
    found = sections(lines)
    if existing := _find(found, title):
        _, start, end = existing
        if "".join(lines[start + 1 : end]).strip():
            return text, "kept"
        # Keep one blank line before the next section, as the templates do.
        tail = ["\n"] if end < len(lines) else []
        return "".join([*lines[: start + 1], inner, *tail, *lines[end:]]), "filled"
    return _add(lines, found, title, inner, before), "added"


def append_to_section(text: str, title: str, content: str, before: str | None = None) -> str:
    """`content` at the end of `## title`, after what it holds; a missing section is added as `fill_section` would."""
    lines = _lines(text)
    inner = content.strip("\n") + "\n"
    found = sections(lines)
    existing = _find(found, title)
    if existing is None:
        return _add(lines, found, title, inner, before)
    _, start, end = existing
    body_end = end
    while body_end > start + 1 and not lines[body_end - 1].strip():
        body_end -= 1
    tail = ["\n"] if end < len(lines) else []
    return "".join([*lines[:body_end], inner, *tail, *lines[end:]])


# --- the `about` note: a `## section` and the `### subsections` inside it (D160) ---------------


def _outside_fences(lines: list[str], start: int, end: int):
    """(index, line) for lines[start:end] that are not inside a code fence."""
    fence: str | None = None
    for i in range(start, end):
        line = lines[i]
        if match := FENCE.match(line):
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not line[len(marker) :].strip():
                fence = None
            continue
        if fence is None:
            yield i, line


def _subs(lines: list[str], parent: tuple[str, int, int]) -> list[tuple[str, int]]:
    """(title, heading line) of each `### ` heading inside a section."""
    _, start, end = parent
    return [(line[4:].strip(), i) for i, line in _outside_fences(lines, start + 1, end) if line.startswith("### ")]


def _span(lines: list[str], parent: tuple[str, int, int], sub: str | None) -> tuple[int, int] | None:
    """(heading line, first line after its text) of the section's own text (`sub` None: up to its first
    `###`) or of one `### sub`; None when that subsection is missing."""
    _, start, end = parent
    subs = _subs(lines, parent)
    if sub is None:
        return start, subs[0][1] if subs else end
    key = sub.strip().casefold()
    for n, (title, i) in enumerate(subs):
        if title.casefold() == key:
            return i, subs[n + 1][1] if n + 1 < len(subs) else end
    return None


def _insert_sub(lines: list[str], parent: tuple[str, int, int], sub: str, inner: str) -> str:
    """A new `### sub` holding `inner` at the end of the parent section."""
    _, start, end = parent
    body_end = end
    while body_end > start + 1 and not lines[body_end - 1].strip():
        body_end -= 1
    tail = ["\n"] if end < len(lines) else []
    return "".join([*lines[:body_end], "\n", f"### {sub.strip()}\n", inner, *tail, *lines[end:]])


def fill_part(
    text: str, title: str, sub: str | None, content: str, before: str | None = None
) -> tuple[str, FillStatus]:
    """`fill_section` for the `about` note: `content` goes under `## title` (its own text, ahead of any
    `###`) or under `### sub` inside it, only when that part is empty or missing."""
    lines = _lines(text)
    inner = content.strip("\n") + "\n"
    found = sections(lines)
    parent = _find(found, title)
    if parent is None:
        block = inner if sub is None else f"### {sub.strip()}\n{inner}"
        return _add(lines, found, title, block, before), "added"
    span = _span(lines, parent, sub)
    if span is None:
        return _insert_sub(lines, parent, sub or "", inner), "added"
    head, stop = span
    if "".join(lines[head + 1 : stop]).strip():
        return text, "kept"
    tail = ["\n"] if stop < len(lines) else []
    return "".join([*lines[: head + 1], inner, *tail, *lines[stop:]]), "filled"


def part_state(text: str, title: str, sub: str | None) -> Literal["empty", "filled"]:
    """`filled` when the section's own text, or the `### sub`, holds anything (a comment counts); else `empty`."""
    lines = _lines(text)
    parent = _find(sections(lines), title)
    span = _span(lines, parent, sub) if parent else None
    if span is None:
        return "empty"
    return "filled" if "".join(lines[span[0] + 1 : span[1]]).strip() else "empty"


def ensure_part(text: str, title: str, sub: str | None, before: str | None = None) -> tuple[str, bool]:
    """The `## title` or `### sub` heading, empty, when it isn't there yet; (text, whether it was added)."""
    lines = _lines(text)
    found = sections(lines)
    parent = _find(found, title)
    if parent is None:
        block = "\n" if sub is None else f"\n### {sub.strip()}\n\n"
        return _add(lines, found, title, block, before), True
    if sub is None or _span(lines, parent, sub) is not None:
        return text, False
    return _insert_sub(lines, parent, sub, "\n"), True


def parts(text: str) -> list[tuple[str, str | None, str]]:
    """(section, subsection or None, text) for each part of `text` that holds something, in order; what
    comes before the first `## ` heading is a part with an empty section title."""
    lines = _lines(text)
    found = sections(lines)
    first = min((s[1] for s in found), default=len(lines))
    out: list[tuple[str, str | None, str]] = []
    if pre := "".join(lines[:first]).strip():
        out.append(("", None, pre))
    for parent in found:
        _, start, end = parent
        subs = _subs(lines, parent)
        bounds = [(None, start, subs[0][1] if subs else end)]
        bounds += [(t, i, subs[n + 1][1] if n + 1 < len(subs) else end) for n, (t, i) in enumerate(subs)]
        for sub, head, stop in bounds:
            if body := "".join(lines[head + 1 : stop]).strip():
                out.append((parent[0], sub, body))
    return out
