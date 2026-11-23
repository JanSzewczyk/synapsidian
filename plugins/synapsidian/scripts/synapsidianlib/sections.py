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
