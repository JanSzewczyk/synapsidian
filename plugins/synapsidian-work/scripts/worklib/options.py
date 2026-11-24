"""Plugin options reach the scripts as arguments: skills substitute `${user_config.<key>}`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable


def given(raw: str | None) -> str | None:
    """The option's value, or None when empty or left unsubstituted (`${user_config.x}`): that source is off."""
    if raw is None:
        return None
    value = raw.strip()
    return None if not value or value.startswith("${") else value


def given_list(raws: str | Iterable[str] | None) -> list[str]:
    """The values of a multi-value option (`multiple: true`), in order and without duplicates.

    Each argument may hold one value or several: a JSON array, or values separated by commas
    or newlines (how Claude Code joins a list in skill content isn't documented, so accept both).
    Empty or unsubstituted arguments contribute nothing; an empty result means the source is off.
    """
    if raws is None:
        return []
    values: list[str] = []
    for raw in [raws] if isinstance(raws, str) else raws:
        value = given(raw)
        if value is None:
            continue
        parsed = _json_list(value)
        parts = parsed if parsed is not None else re.split(r"[,\n]", value)
        values += [part.strip() for part in parts if part.strip() and not part.strip().startswith("${")]
    return list(dict.fromkeys(values))


def _json_list(value: str) -> list[str] | None:
    if not value.startswith("["):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return [str(item) for item in parsed] if isinstance(parsed, list) else None
