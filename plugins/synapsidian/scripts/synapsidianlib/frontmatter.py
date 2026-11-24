"""Read and write YAML frontmatter the way Obsidian does: a `---` fenced block on line 1.

Scalars are typed by the YAML 1.2 core schema, as Obsidian reads them, not PyYAML's YAML 1.1
default: `10:30` stays the text "10:30" (1.1 reads 630), `0123` is 123 (1.1: octal 83), and
`yes`, `no`, `on`, `off` stay words (1.1: booleans). Every write re-dumps the whole block, so
under 1.1 a key synapsidian never touched changed value on the next `note set` (D121). Dates keep
PyYAML's timestamp type: Obsidian's date properties are written that way and synapsidian compares them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

FENCE = "---"

_BOOL, _INT, _FLOAT = "tag:yaml.org,2002:bool", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float"
_CORE_RESOLVERS = (
    (_BOOL, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")),
    (_INT, re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789")),
    (
        _FLOAT,
        re.compile(
            r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
        ),
        list("-+0123456789."),
    ),
)


def _core_schema(cls: type) -> type:
    """`cls` with PyYAML's YAML 1.1 bool/int/float resolvers replaced by the 1.2 core schema's."""
    cls.yaml_implicit_resolvers = {  # type: ignore[attr-defined]
        first: [(tag, regexp) for tag, regexp in resolvers if tag not in (_BOOL, _INT, _FLOAT)]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    for tag, regexp, first in _CORE_RESOLVERS:
        cls.add_implicit_resolver(tag, regexp, first)  # type: ignore[attr-defined]
    return cls


def _construct_int(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> int:
    value = str(loader.construct_scalar(node))
    if value.startswith(("0o", "0x")):
        return int(value[2:], 8 if value[1] == "o" else 16)
    return int(value, 10)  # a leading zero is decimal in YAML 1.2, never octal


@_core_schema
class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor(_INT, _construct_int)


@dataclass(frozen=True, slots=True)
class Parsed:
    meta: dict[str, Any] | None  # None when the note has no frontmatter block
    body: str
    error: str | None = None


def normalize_newlines(text: str) -> str:
    return text.removeprefix("﻿").replace("\r\n", "\n")


def parse(text: str) -> Parsed:
    text = normalize_newlines(text)
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != FENCE:
        return Parsed(None, text)
    end = next((i for i, line in enumerate(lines[1:], start=1) if line.rstrip() == FENCE), None)
    if end is None:
        return Parsed(None, text, "frontmatter has no closing ---")

    raw = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    try:
        meta = yaml.load(raw, Loader=_Loader) if raw.strip() else {}  # _Loader is a SafeLoader subclass
    except yaml.YAMLError as exc:
        return Parsed(None, body, f"frontmatter is not valid YAML: {exc}".splitlines()[0])
    if not isinstance(meta, dict):
        return Parsed(None, body, "frontmatter is not a key/value mapping")
    return Parsed(meta, body)


@_core_schema
class _NoAliasDumper(yaml.SafeDumper):
    """Never write `&id001` / `*id001`: Obsidian's property editor doesn't resolve YAML aliases,
    and PyYAML emits them whenever one object (say, today's date) fills two fields."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


# An empty property is written `key:`, as Obsidian writes it, not `key: null`.
_NoAliasDumper.add_representer(type(None), lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""))


def dump(meta: dict[str, Any], body: str) -> str:
    """Serialise frontmatter + body. Key order is preserved; lists use block style."""
    yaml_text = yaml.dump(
        meta, Dumper=_NoAliasDumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=10_000
    )
    body = body.lstrip("\n")
    return f"{FENCE}\n{yaml_text}{FENCE}\n{body}" if body else f"{FENCE}\n{yaml_text}{FENCE}\n"
