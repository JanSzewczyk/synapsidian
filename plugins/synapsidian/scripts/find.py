#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Ranked keyword search over the vault (stage 1 of D20).

  find.py --vault V "how do we export payroll data" [--type task] [--limit 8] [--all]
  find.py --eval questions.jsonl [--all]      recall@1 / recall@5 / MRR over a question set
  find.py --related "Note title" [--type T]   notes most like that one, each with `linked` (D127)

Scores each note with BM25 per field (title, aliases, summary, tags, body), weighted
so a hit in the title or summary outweighs one buried in the body. Prints JSON hits.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from synapsidianlib import config, vault

WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_STOPWORDS_TEXT = """a an and are as at be been but by can could did do does doing for from had has have how i if
in into is it its me my no not of on or our should so than that the their them then there these they this to was
we were what when where which who why will with would you your about any all also just done get got make made more
most much some such use used using via vs"""
STOPWORDS = frozenset(_STOPWORDS_TEXT.split())
FIELD_WEIGHTS = {"title": 5.0, "aliases": 4.0, "summary": 3.0, "tags": 2.0, "properties": 2.0, "body": 1.0}
# "1:1", "1-1", "one on one", "one-on-one" are one concept; meeting notes use the first two.
ONE_ON_ONE = re.compile(r"(?<![\w.])(?:1\s*[-:]\s*1|one[\s-]+on[\s-]+one)(?![\w.])")
# Frontmatter that identifies rather than describes; kept out of the `properties` field.
UNSEARCHED_PROPERTIES = frozenset(
    {"type", "created", "summary", "tags", "aliases", "content_hash", "scanned_commit", "event_id", "url", "source_url"}
)
TYPE_WEIGHTS = {"capture": 0.8, "daily": 0.6}
DONE_STATUSES = {"done", "dropped", "superseded", "graduated"}
K1, B = 1.2, 0.75


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return ONE_ON_ONE.sub(" oneonone ", plain)


def stem(word: str) -> str:
    """Light English suffix stripping, enough to match plural/verb forms."""
    for suffix, keep in (("ies", "y"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3 and not word.endswith("ss"):
            return word[: -len(suffix)] + keep
    return word


def terms(text: str) -> list[str]:
    return [stem(w) for w in WORD.findall(fold(text)) if w not in STOPWORDS and len(w) > 1]


@dataclass(slots=True)
class Doc:
    note: vault.Note
    fields: dict[str, Counter[str]]
    lengths: dict[str, int]


def to_text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return "" if value is None else str(value)


def make_doc(note: vault.Note) -> Doc:
    raw = {
        "title": note.title,
        "aliases": to_text(note.get("aliases")),
        "summary": to_text(note.get("summary")),
        "tags": to_text(note.get("tags")).replace("-", " "),
        "properties": " ".join(
            to_text(value).replace("[[", " ").replace("]]", " ")
            for key, value in (note.meta or {}).items()
            if key not in UNSEARCHED_PROPERTIES and not str(value).startswith("http")
        ),
        "body": note.body,
    }
    fields = {name: Counter(terms(text)) for name, text in raw.items()}
    return Doc(note, fields, {name: sum(c.values()) for name, c in fields.items()})


def snippet(body: str, query_terms: set[str], width: int = 180) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("<!--", "#")) and query_terms & set(terms(stripped)):
            return stripped[:width]
    first = next((ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith(("<!--", "#"))), "")
    return first[:width]


def search(docs: list[Doc], query: str, limit: int, type_filter: str | None) -> list[dict[str, object]]:
    q_terms = list(dict.fromkeys(terms(query)))
    if not q_terms or not docs:
        return []
    n = len(docs)
    avg_len = {f: (sum(d.lengths[f] for d in docs) / n) or 1.0 for f in FIELD_WEIGHTS}
    df = {t: sum(1 for d in docs if any(d.fields[f][t] for f in FIELD_WEIGHTS)) for t in q_terms}
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q_terms}
    phrase = fold(query).strip()

    hits = []
    for doc in docs:
        note = doc.note
        if type_filter and note.type != type_filter:
            continue
        score = 0.0
        matched: set[str] = set()
        for t in q_terms:
            for f, weight in FIELD_WEIGHTS.items():
                tf = doc.fields[f][t]
                if not tf:
                    continue
                matched.add(t)
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * doc.lengths[f] / avg_len[f]))
                score += weight * idf[t] * norm
        if not score:
            continue
        # Reward notes that cover more of the question, not one term many times.
        score *= 0.5 + 0.5 * len(matched) / len(q_terms)
        if len(phrase) > 3 and (phrase in fold(note.title) or phrase in fold(to_text(note.get("summary")))):
            score *= 1.5
        score *= TYPE_WEIGHTS.get(note.type or "", 1.0)
        if str(note.get("status", "")) in DONE_STATUSES:
            score *= 0.8
        hits.append((score, note.mtime, note, matched))

    hits.sort(key=lambda h: (h[0], h[1]), reverse=True)
    return [
        {
            "rel": note.rel,
            "path": str(note.path),
            "title": note.title,
            "type": note.type,
            "summary": note.get("summary"),
            "status": note.get("status"),
            "score": round(score, 3),
            "matched": sorted(matched),
            "snippet": snippet(note.body, matched),
        }
        for score, _, note, matched in hits[:limit]
    ]


RELATED_BODY_TERMS = 12  # the body's most distinctive words that join the title, summary and tags
NOT_RELATED_TYPES = {"daily", "review", "capture"}  # logs: sharing words with them says nothing


def related(docs: list[Doc], target: Doc, limit: int) -> list[dict[str, object]]:
    """Notes most like `target` (D127): BM25 with a query made of its title, aliases, summary and
    tags plus the body words rarest in the vault. Lexical, like the rest of find (D83). Each hit
    says whether the two notes already link to each other."""
    n = len(docs) or 1
    df = Counter(t for d in docs for t in {t for f in FIELD_WEIGHTS for t in d.fields[f]})
    body = target.fields["body"]
    distinctive = sorted(body, key=lambda t: -body[t] * math.log(1 + n / (df[t] or 1)))[:RELATED_BODY_TERMS]
    head = " ".join(to_text(target.note.get(k)) for k in ("aliases", "summary", "tags"))
    query = f"{target.note.title} {head} {' '.join(distinctive)}"
    pool = [d for d in docs if d.note.rel != target.note.rel and d.note.type not in NOT_RELATED_TYPES]
    hits = search(pool, query, limit, None)
    title = target.note.title.casefold()
    for hit in hits:
        other = next(d for d in pool if d.note.rel == hit["rel"])
        hit["linked"] = f"[[{title}" in other.note.body.casefold() or f"[[{str(hit['title']).casefold()}" in (
            target.note.body.casefold()
        )
    return hits


def evaluate(docs: list[Doc], cases: list[dict[str, object]]) -> dict[str, object]:
    """Recall@1, recall@5 and MRR of `search` on cases `{"q": ..., "expect": title, path or a list}` (D82)."""
    ranks: list[int | None] = []
    misses: list[dict[str, object]] = []
    for case in cases:
        wanted = case["expect"] if isinstance(case["expect"], list) else [case["expect"]]
        expected = {Path(str(t)).stem.casefold() if str(t).endswith(".md") else str(t).casefold() for t in wanted}
        titles = [str(h["title"]) for h in search(docs, str(case["q"]), 10, None)]
        rank = next((i for i, t in enumerate(titles, start=1) if t.casefold() in expected), None)
        ranks.append(rank)
        if rank is None or rank > 5:
            misses.append({"q": case["q"], "expect": case["expect"], "rank": rank, "top3": titles[:3]})
    total = len(ranks) or 1
    return {
        "ok": True,
        "cases": len(ranks),
        "recall_at_1": round(sum(r == 1 for r in ranks) / total, 3),
        "recall_at_5": round(sum(r is not None and r <= 5 for r in ranks) / total, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / total, 3),
        "misses": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--vault")
    parser.add_argument("--type", help="only notes of this type")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--all", action="store_true", help="include Archive/ and Sources/")
    parser.add_argument("--eval", metavar="FILE", help='JSONL of {"q", "expect": [titles]}: report recall instead')
    parser.add_argument("--related", metavar="NOTE", help="notes most like this one (its title or vault-relative path)")
    args = parser.parse_args()
    if not args.query and not args.eval and not args.related:
        parser.error("give a query, --related NOTE or --eval FILE")

    vault_root = config.vault_path(args.vault)
    if vault_root is None or not vault_root.is_dir():
        print(json.dumps({"ok": False, "error": "vault not found; run /synapsidian:setup"}))
        sys.exit(2)

    started = time.perf_counter()
    docs = [make_doc(n) for n in vault.iter_notes(vault_root, include_cold=args.all)]
    if args.eval:
        lines = Path(args.eval).expanduser().read_text(encoding="utf-8").splitlines()
        cases = [json.loads(line) for line in lines if line.strip()]
        print(json.dumps(evaluate(docs, cases), ensure_ascii=False))
        return
    if args.related:
        wanted = args.related.removesuffix(".md")
        target = next(
            (
                d
                for d in docs
                if d.note.rel.removesuffix(".md") == wanted or d.note.title.casefold() == wanted.casefold()
            ),
            None,
        )
        if target is None:
            print(json.dumps({"ok": False, "error": f"no note {args.related!r}"}))
            sys.exit(2)
        hits = related(docs, target, args.limit)
        if args.type:
            hits = [h for h in hits if h["type"] == args.type]
        print(json.dumps({"ok": True, "related_to": target.note.rel, "hits": hits}, ensure_ascii=False, default=str))
        return
    hits = search(docs, args.query, args.limit, args.type)
    print(
        json.dumps(
            {
                "ok": True,
                "query": args.query,
                "searched": len(docs),
                "scope": "all folders" if args.all else "all folders except Archive/ and Sources/",
                "ms": round((time.perf_counter() - started) * 1000),
                "hits": hits,
            },
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
