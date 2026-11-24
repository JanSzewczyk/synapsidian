"""Source notes: canonical text, content hash, URL normalisation and dedup lookup (D75).

Pure functions only (no network), shared by `source.py` and the tests.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

from . import schema, vault

# Query parameters that identify a click, not a page.
TRACKING_PARAM = re.compile(
    r"(utm_[a-z_]+|fbclid|gclid|dclid|gbraid|wbraid|msclkid|mc_cid|mc_eid|igshid|yclid|_hsenc|_hsmi|ref|ref_src|si)"
)
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YOUTUBE_HOSTS = frozenset({"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"})
UNCHANGED_RATIO = 0.98
SOURCE_FOLDERS = ("Sources", "Archive/Sources")


def canonical(text: str) -> str:
    """Text reduced to what survives a re-capture: no BOM, one list marker, single spaces."""
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?m)^(\s*)[*+](\s+)", r"\1-\2", text)
    return " ".join(text.split())


def content_hash(text: str) -> str:
    return hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()[:16]


# --- quote check (D125) -------------------------------------------------------------------

_TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-"})
_MARKUP = re.compile(r"[*_`]|\[([^\]]*)\]\([^)]*\)")
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…|\[\.\.\.\]|\[…\])\s*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _plain(text: str) -> str:
    """Text as a reader sees it: no emphasis or link syntax, plain quotes and dashes, one space."""
    text = unicodedata.normalize("NFKC", text).translate(_TYPOGRAPHY)
    text = _MARKUP.sub(lambda m: m.group(1) or "", text)
    return " ".join(text.casefold().split())


def quote_found(source: str, quote: str) -> bool:
    """True when `quote` is in `source` word for word, ignoring case, markup, typographic quotes
    and spacing. An ellipsis in the quote stands for left-out text: its parts must appear in order."""
    haystack, position = _plain(source), 0
    for part in (_plain(p) for p in _ELLIPSIS.split(quote.strip().strip("\"'“”")) if p.strip()):
        found = haystack.find(part, position)
        if found < 0:
            return False
        position = found + len(part)
    return position > 0


def closest_passage(source: str, quote: str) -> str | None:
    """The source sentence sharing the most words with `quote`, to show what it really says."""
    wanted = set(_plain(quote).split())
    best, score = None, 0.0
    for sentence in _SENTENCE.split(source):
        words = set(_plain(sentence).split())
        if words and (overlap := len(wanted & words) / len(wanted | words)) > score:
            best, score = " ".join(sentence.split()), overlap
    return best[:400] if best and score >= 0.2 else None


def youtube_id(target: str) -> str | None:
    """The 11-character video id of a YouTube watch, short, shorts, embed or live link."""
    parts = urlsplit(target if "://" in target else f"https://{target}")
    host = (parts.hostname or "").removeprefix("www.")
    candidate = ""
    if host == "youtu.be":
        candidate = parts.path.strip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS:
        if parts.path == "/watch":
            candidate = parse_qs(parts.query).get("v", [""])[0]
        elif match := re.match(r"/(?:shorts|embed|live|v)/([^/]+)", parts.path):
            candidate = match.group(1)
    return candidate if VIDEO_ID.fullmatch(candidate) else None


def normalize_url(url: str) -> str:
    """Comparison key for a URL: no scheme, `www.`, default port, trailing slash, fragment or tracking."""
    url = url.strip()
    if video := youtube_id(url):
        return f"youtube.com/watch?v={video}"
    if url.startswith("file://"):
        return url
    parts = urlsplit(url if "://" in url else f"https://{url}")
    host = (parts.hostname or "").lower().removeprefix("www.")
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAM.fullmatch(k))
    )
    return f"{host}{port}{parts.path.rstrip('/')}" + (f"?{query}" if query else "")


def similarity(a: str, b: str, size: int = 4) -> float:
    """Overlap of word 4-grams between two texts, 0..1. Linear time; changing one word
    touches at most four shingles, so long texts with a changed date or counter stay ~1."""
    shingles_a, shingles_b = _shingles(canonical(a), size), _shingles(canonical(b), size)
    if not shingles_a or not shingles_b:
        return 1.0 if shingles_a == shingles_b else 0.0
    shared = sum((shingles_a & shingles_b).values())
    return shared / max(shingles_a.total(), shingles_b.total())


def _shingles(text: str, size: int) -> Counter[tuple[str, ...]]:
    words = text.casefold().split()
    return Counter(tuple(words[i : i + size]) for i in range(max(len(words) - size + 1, 1)))


def existing(vault_root: Path) -> list[vault.Note]:
    """Every source note, archived ones included."""
    found: list[vault.Note] = []
    for folder in SOURCE_FOLDERS:
        base = vault_root / folder
        if base.is_dir():
            found += [
                note
                for path in sorted(base.rglob("*.md"))
                if (note := vault.read_note(vault_root, path)).type == "source"
            ]
    return found


def by_url(notes: list[vault.Note], url: str) -> list[vault.Note]:
    """Notes for the same normalised URL, newest first: by fetch date, and on the same day a
    note that another one `supersedes` comes after it."""
    key = normalize_url(url)
    same = [n for n in notes if isinstance(n.get("url"), str) and normalize_url(n.get("url")) == key]
    replaced = {str(n.get("supersedes", "")).strip("[]") for n in same}
    return sorted(same, key=lambda n: (str(n.get("fetched_at") or ""), n.title not in replaced), reverse=True)


def match(vault_root: Path, *, url: str | None, text: str) -> tuple[str, vault.Note | None]:
    """('unchanged', note) for a source already in the vault, ('changed', previous) for a new
    version of a known URL, ('new', None) otherwise."""
    notes = existing(vault_root)
    digest = content_hash(text)
    if hit := next((n for n in notes if n.get("content_hash") == digest), None):
        return "unchanged", hit
    if url and (same := by_url(notes, url)):
        latest = same[0]
        return ("unchanged" if similarity(latest.body, text) >= UNCHANGED_RATIO else "changed"), latest
    return "new", None


def short_title(title: str, limit: int = 90) -> str:
    """A filename-safe title without emoji, cut at a word boundary."""
    title = "".join(ch for ch in unicodedata.normalize("NFC", title) if not _decoration(ch))
    title = schema.clean_title(title)
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" -,.;") or title[:limit]


def _decoration(ch: str) -> bool:
    """Emoji and pictographs, their variation selectors and joiners."""
    return unicodedata.category(ch) in ("So", "Cs", "Co") or ch in "\N{ZERO WIDTH JOINER}\N{VARIATION SELECTOR-16}"


def chunks(text: str, budget: int = 40_000) -> list[tuple[int, int]]:
    """1-based inclusive line ranges of about `budget` characters, for splitting the reading.
    A tail under a quarter of the budget joins the previous range instead of standing alone."""
    ranges: list[tuple[int, int]] = []
    start, size = 1, 0
    lines = text.split("\n")
    for number, line in enumerate(lines, start=1):
        size += len(line) + 1
        if size >= budget and number < len(lines):
            ranges.append((start, number))
            start, size = number + 1, 0
    if ranges and size < budget // 4:
        ranges[-1] = (ranges[-1][0], len(lines))
    else:
        ranges.append((start, len(lines)))
    return ranges
