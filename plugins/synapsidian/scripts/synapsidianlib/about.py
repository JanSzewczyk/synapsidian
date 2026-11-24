"""The user's own vault rules in `About.md` (D92): a `## Rules` section and the `protected` field."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def strip_comments(text: str) -> str:
    return _COMMENT.sub("", text)


def split_rules(body: str) -> tuple[str, str | None]:
    """(body without the Rules section, the section's content or None when there is no such heading).

    The section runs from `## Rules` (any case) to the next heading of level 1 or 2.
    """
    lines = body.split("\n")
    headings = [(i, len(m[1]), m[2].casefold()) for i, ln in enumerate(lines) if (m := _HEADING.match(ln))]
    start = next((i for i, level, title in headings if level == 2 and title == "rules"), None)
    if start is None:
        return body, None
    end = next((i for i, level, _ in headings if i > start and level <= 2), len(lines))
    return "\n".join(lines[:start] + lines[end:]), "\n".join(lines[start + 1 : end])


def rule_lines(section: str) -> list[str]:
    """The rules as the user wrote them, without comments and blank lines."""
    return [ln.rstrip() for ln in strip_comments(section).split("\n") if ln.strip()]


def protected_paths(value: object) -> list[PurePosixPath]:
    """Vault-relative folders or files from the `protected` field; anything else is ignored."""
    items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    paths = []
    for item in items:
        if not isinstance(item, str):
            continue
        path = PurePosixPath(item.strip().strip("/"))
        if path.parts and ".." not in path.parts and not path.is_absolute():
            paths.append(path)
    return paths


def _fold(part: str) -> str:
    return unicodedata.normalize("NFC", part).casefold()


def is_protected(rel: PurePosixPath, protected: list[PurePosixPath]) -> PurePosixPath | None:
    """The protected entry that covers `rel`, compared as macOS and Windows file systems compare
    names: ignoring letter case and Unicode normalisation form (an NFD `Żółw` is the NFC folder)."""
    parts = tuple(_fold(p) for p in rel.parts)
    for entry in protected:
        wanted = tuple(_fold(p) for p in entry.parts)
        if parts[: len(wanted)] == wanted:
            return entry
    return None
