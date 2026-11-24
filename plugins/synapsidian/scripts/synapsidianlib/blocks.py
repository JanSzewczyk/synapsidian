"""Generated blocks: `<!-- @generated:<name>[ sha=<12 hex>] -->` ... `<!-- @end -->` (block.py, D81)."""

from __future__ import annotations

import hashlib
import re

OPEN = "<!-- @generated:"
END = "<!-- @end -->"
# A block's content never runs over another block's opening line. Without that, a block whose
# `@end` line was deleted would reach the next block's `@end` and a `set` would replace all the
# user's text in between (D121).
INNER = rf"(?:(?!^{re.escape(OPEN)}).)*?"
ANY_BLOCK = re.compile(
    rf"{re.escape(OPEN)}([\w-]+)(?: sha=([0-9a-f]{{12}}))? -->\n({INNER})^{re.escape(END)}", re.S | re.M
)
ANY_OPENING = re.compile(rf"^{re.escape(OPEN)}([\w-]+)(?: sha=[0-9a-f]{{12}})? -->$", re.M)


def broken(text: str) -> list[str]:
    """Names of blocks whose opening line has no `@end` before the next block opens."""
    whole = {m.start() for m in ANY_BLOCK.finditer(text)}
    return [m.group(1) for m in ANY_OPENING.finditer(text) if m.start() not in whole]


def digest(inner: str) -> str:
    return hashlib.sha256(inner.strip().encode("utf-8")).hexdigest()[:12]


def rehash_intact(before: str, after: str) -> str:
    """`after` with the hash of each block that matched its hash in `before` recomputed.

    For a mechanical rewrite synapsidian makes itself (a renamed link): the block stays "not edited
    by hand". A block that was already edited keeps its stale hash, so it still reads as edited.
    """
    intact = {m.group(1) for m in ANY_BLOCK.finditer(before) if m.group(2) and digest(m.group(3)) == m.group(2)}

    def refresh(match: re.Match[str]) -> str:
        name, stored, inner = match.group(1), match.group(2), match.group(3)
        if name not in intact or not stored:
            return match.group(0)
        return match.group(0).replace(f"sha={stored}", f"sha={digest(inner)}", 1)

    return ANY_BLOCK.sub(refresh, after)
