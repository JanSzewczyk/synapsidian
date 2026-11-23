from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from find import make_doc, search, terms
from synapsidianlib import vault as vault_mod

QUESTIONS = yaml.safe_load((Path(__file__).parent / "fixtures" / "search_questions.yaml").read_text())


def test_questions_do_not_leak_their_target_titles():
    """A question sharing title words with its answer measures nothing (lesson from the reference)."""
    for case in QUESTIONS:
        shared = set(terms(case["q"])) & set(terms(Path(case["expect"]).stem))
        assert len(shared) <= 1, (case["q"], shared)


@pytest.fixture(scope="module")
def docs():
    root = Path(__file__).parent / "fixtures" / "vault"
    return [make_doc(n) for n in vault_mod.iter_notes(root)]


@pytest.mark.parametrize("case", QUESTIONS, ids=[c["q"][:40] for c in QUESTIONS])
def test_paraphrased_question_finds_its_note_in_top_5(docs, case):
    hits = [h["rel"] for h in search(docs, case["q"], limit=5, type_filter=None)]
    assert case["expect"] in hits, hits


def test_type_filter_and_empty_query(docs):
    hits = search(docs, "export", limit=10, type_filter="task")
    assert hits and all(h["type"] == "task" for h in hits)
    assert search(docs, "the of and", limit=5, type_filter=None) == []


def test_done_tasks_rank_below_open_ones_for_the_same_words(docs):
    assert search(docs, "rounding", limit=5, type_filter=None)[0]["rel"] == "Notes/Rounding in statistics service.md"


def test_one_on_one_spellings_meet_and_properties_are_searched(tmp_path):
    assert terms("1:1 with Anna") == terms("one-on-one with Anna") == terms("One on one with anna")
    assert "oneonone" in terms("2026-10-19 1-1 Mikael") and "oneonone" not in terms("version 1.1.0")
    person = tmp_path / "People" / "Mikael.md"
    person.parent.mkdir()
    person.write_text("---\ntype: person\nsummary: s\nrelationship: manager\nurl: https://x.test/manager\n---\nBody\n")
    doc = make_doc(vault_mod.read_note(tmp_path, person))
    assert doc.fields["properties"]["manager"] == 1  # the URL isn't indexed
    assert search([doc], "my manager", limit=5, type_filter=None)[0]["title"] == "Mikael"


def test_eval_reports_recall(run, fixture_vault, tmp_path):
    cases = tmp_path / "q.jsonl"
    cases.write_text(
        '{"q": "pay gap after controls", "expect": "Notes/Adjusted pay gap.md"}\n'
        '{"q": "zzz nothing matches", "expect": ["Adjusted pay gap"]}\n'
    )
    code, result = run("find", "--eval", str(cases), vault=fixture_vault)
    assert code == 0 and result["cases"] == 2 and result["recall_at_1"] == 0.5 and result["recall_at_5"] == 0.5
    assert result["misses"][0]["q"] == "zzz nothing matches" and result["misses"][0]["rank"] is None


def test_related_finds_notes_on_the_same_subject_and_says_which_are_linked(run, fixture_vault):
    """D127: `--related` builds a query from the note itself; logs and the note itself are left out."""
    code, out = run("find", "--related", "Adjusted pay gap", "--limit", "5", vault=fixture_vault)
    assert code == 0 and out["related_to"] == "Notes/Adjusted pay gap.md"
    titles = [h["title"] for h in out["hits"]]
    assert "Adjusted pay gap" not in titles and {"Pay equity export", "EU pay transparency directive"} <= set(
        titles[:3]
    )
    assert all(h["type"] not in ("daily", "review", "capture") for h in out["hits"])
    assert all(isinstance(h["linked"], bool) for h in out["hits"])
    note = fixture_vault / "Notes" / "Adjusted pay gap.md"
    note.write_text(note.read_text() + "\nSee [[EU pay transparency directive]].\n")
    _, again = run("find", "--related", "Notes/Adjusted pay gap.md", vault=fixture_vault)
    assert next(h for h in again["hits"] if h["title"] == "EU pay transparency directive")["linked"] is True
    assert run("find", "--related", "No such note", vault=fixture_vault)[0] == 2


def test_cli_reports_scope_and_counts(run, fixture_vault):
    code, result = run("find", "pay gap after controls", vault=fixture_vault)
    assert code == 0 and result["searched"] == 30
    assert result["hits"][0]["rel"] == "Notes/Adjusted pay gap.md"
    assert "Archive" in result["scope"]
