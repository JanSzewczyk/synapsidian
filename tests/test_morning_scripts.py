from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

NOW = "2026-10-14T09:00:00+02:00"  # Wednesday


def pr(number: int, **fields: object) -> dict:
    base = {
        "number": number,
        "title": f"PR {number}",
        "url": f"https://github.com/o/r/pull/{number}",
        "isDraft": False,
        "createdAt": "2026-10-13T08:00:00Z",
        "reviewDecision": "REVIEW_REQUIRED",
        "mergeable": "MERGEABLE",
        "statusCheckRollup": [{"__typename": "CheckRun", "conclusion": "SUCCESS", "status": "COMPLETED"}],
        "latestReviews": [],
        "commits": [{"committedDate": "2026-10-13T08:00:00Z"}],
    }
    return {**base, **fields}


def review(login: str, state: str, at: str) -> dict:
    return {"author": {"login": login}, "state": state, "submittedAt": at}


@pytest.fixture
def classify(run, tmp_path: Path):
    def _classify(mine: list[dict], requested: list[dict] | None = None) -> dict:
        data = tmp_path / "prs.json"
        data.write_text(json.dumps({"mine": mine, "requested": requested or []}))
        code, out = run("prs", "--from-json", str(data), "--now", NOW, "--repo", "o/r")
        assert code == 0, out
        return out

    return _classify


def test_ready_stuck_and_in_review(classify):
    out = classify(
        [
            pr(1, reviewDecision="APPROVED", latestReviews=[review("anna", "APPROVED", "2026-10-13T10:00:00Z")]),
            pr(2, statusCheckRollup=[{"conclusion": "FAILURE"}]),
            pr(3, mergeable="CONFLICTING"),
            pr(4),
            pr(5, createdAt="2026-10-09T08:00:00Z"),  # Friday: 3 working days, still nobody human reviewed
            pr(
                6,
                latestReviews=[review("coderabbitai", "APPROVED", "2026-10-09T09:00:00Z")],
                createdAt="2026-10-09T08:00:00Z",
            ),
        ]
    )
    assert [e["number"] for e in out["ready"]] == [1]
    stuck = {e["number"]: e["reasons"] for e in out["stuck"]}
    assert stuck[2] == ["failing checks"] and stuck[3] == ["merge conflict"]
    assert stuck[5] == ["no review for 3 working days"]
    assert stuck[6] == ["no review for 3 working days"]  # a bot's approval isn't a review
    assert [e["number"] for e in out["in_review"]] == [4]


def test_changes_requested_only_stuck_until_a_new_push(classify):
    asked = [review("anna", "CHANGES_REQUESTED", "2026-10-13T12:00:00Z")]
    out = classify(
        [
            pr(1, reviewDecision="CHANGES_REQUESTED", latestReviews=asked),
            pr(
                2,
                reviewDecision="CHANGES_REQUESTED",
                latestReviews=asked,
                commits=[{"committedDate": "2026-10-13T15:00:00Z"}],
            ),
        ]
    )
    assert {e["number"]: e["reasons"] for e in out["stuck"]} == {1: ["changes requested, no push since"]}
    assert [e["number"] for e in out["in_review"]] == [2]


def test_approved_and_green_too_long_is_stuck_and_drafts_age(classify):
    out = classify(
        [
            pr(1, reviewDecision="APPROVED", latestReviews=[review("anna", "APPROVED", "2026-10-08T10:00:00Z")]),
            pr(2, isDraft=True, createdAt="2026-10-01T08:00:00Z"),
            pr(3, isDraft=True),
        ]
    )
    assert out["stuck"][0]["reasons"] == ["approved and green but unmerged for 4 working days"]
    assert [(e["number"], e["reasons"]) for e in out["draft"]] == [(2, ["draft for 12 days"]), (3, [])]


def test_escalations(classify):
    out = classify(
        [pr(1, statusCheckRollup=[{"conclusion": "FAILURE"}], commits=[{"committedDate": "2026-10-08T08:00:00Z"}])],
        requested=[pr(9, createdAt="2026-10-08T08:00:00Z"), pr(10), pr(11, isDraft=True)],
    )
    assert [e["number"] for e in out["waiting_on_me"]] == [9, 10]
    assert sorted(e["number"] for e in out["escalate"]) == [1, 9]


def test_query_filters_dates_links_and_titles(run, fixture_vault):
    def titles(*args: str) -> list[str]:
        code, out = run("query", "notes", *args, vault=fixture_vault)
        assert code == 0, out
        return [n["title"] for n in out["notes"]]

    assert titles("--type", "task", "--where", "status!=done", "--where", "due<=2026-10-20") == [
        "T1 Review export TDD"
    ]  # undated open tasks never match a date comparison
    assert titles("--type", "task", "--where", "due=") == [
        "T2 Migrate filter panel",
        "T3 Ask marketing for deck template",
        "T4 Fix percent totals",
    ]
    assert titles("--type", "meeting", "--where", "attendees=[[Anna Nowak]]") == ["2026-10-09 review Export demo"]
    assert titles("--where", "title~bonus") == ["Bonus calculation"]
    assert titles("--type", "task", "--where", "done_on>=2026-10-01") == ["T4 Fix percent totals"]
    assert run("query", "notes", "--where", "nonsense", vault=fixture_vault)[0] == 2


def test_query_commits_since_the_last_morning(run, vault):
    def commit(skill: str, name: str) -> None:
        (vault / name).write_text(name)
        run("commit", "--skill", skill, "--message", name, name, vault=vault)

    commit("evening", "a.md")
    commit("morning", "b.md")
    commit("evening", "c.md")
    commit("task", "d.md")
    commit("save", "e.md")
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    _, out = run("query", "commits", "--today", tomorrow, vault=vault)
    assert [(c["subject"], c["files"]) for c in out["commits"]] == [
        ("synapsidian(save): e.md", ["e.md"]),
        ("synapsidian(evening): c.md", ["c.md"]),
    ]
    # A second morning run the same day: today's own morning commit doesn't end the window,
    # so the overnight list is the same as the first run's (plus what ran in between).
    _, again = run("query", "commits", vault=vault)
    assert [c["subject"] for c in again["commits"]] == [
        "synapsidian(save): e.md",
        "synapsidian(evening): c.md",
        "synapsidian(evening): a.md",
    ]


def test_overnight_lists_a_run_obsidian_git_committed_first(run, vault):
    """D129: the evening's files went into Obsidian Git's commit; overnight still names the run."""
    (vault / "a.md").write_text("a")
    run("commit", "--skill", "morning", "--message", "yesterday", "a.md", vault=vault)
    (vault / "devlog.md").write_text("bullets")
    subprocess.run(["git", "-C", str(vault), "add", "devlog.md"], check=True)
    subprocess.run(["git", "-C", str(vault), "commit", "-qm", "vault backup: 2026-10-30 20:10"], check=True)
    _, out = run("commit", "--skill", "evening", "--message", "devlog", "devlog.md", vault=vault)
    assert out["committed"] is False and out["swept"]
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    _, overnight = run("query", "commits", "--skills", "evening", "--today", tomorrow, vault=vault)
    assert [(c["subject"], c["files"], c.get("swept")) for c in overnight["commits"]] == [
        ("synapsidian(evening): devlog", ["devlog.md"], True)
    ]


def test_watched_research_is_due_when_its_interval_has_passed(run, vault):
    """D134: `watch` on a dossier; `refreshed` (else `created`) dates it."""
    (vault / "Research").mkdir()
    head = "---\ntype: research\ncreated: {c}\nsummary: s\nquestion: q{n}\n{extra}---\n"
    (vault / "Research" / "A.md").write_text(head.format(c="2026-10-01", n=1, extra="watch: weekly\n"))
    (vault / "Research" / "B.md").write_text(
        head.format(c="2026-10-01", n=2, extra="watch: weekly\nrefreshed: 2026-10-28\n")
    )
    (vault / "Research" / "C.md").write_text(head.format(c="2026-10-01", n=3, extra=""))
    (vault / "Research" / "D.md").write_text(head.format(c="2026-10-20", n=4, extra="watch: monthly\n"))
    _, out = run("query", "watched", "--today", "2026-10-30", vault=vault)
    assert [(d["title"], d["since"]) for d in out["due"]] == [("A", "2026-10-01")]
    _, later = run("query", "watched", "--today", "2026-11-20", vault=vault)
    assert [d["title"] for d in later["due"]] == ["A", "D", "B"]
    code, _ = run("note", "set", "--file", "Research/C.md", "--field", "watch=daily", vault=vault)
    assert code == 2  # weekly, monthly or quarterly only


def test_resurface_picks_old_linked_knowledge_and_rotates(run, vault):
    """D132: notes unchanged for --days, most linked-to first, each shown once per --quiet-days."""
    import os

    head = "---\ntype: {t}\ncreated: 2026-01-01\nsummary: s\n{extra}---\n{body}\n"
    (vault / "Notes").mkdir()
    (vault / "Decisions").mkdir()
    (vault / "Notes" / "Hub.md").write_text(head.format(t="note", extra="", body="Body"))
    (vault / "Notes" / "Side.md").write_text(head.format(t="note", extra="", body="See [[Hub]]."))
    (vault / "Notes" / "Other.md").write_text(head.format(t="note", extra="", body="Also [[hub]] and [[Side]]."))
    (vault / "Decisions" / "Old.md").write_text(head.format(t="decision", extra="status: superseded\n", body="x"))
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-01-02T10:00:00", "GIT_AUTHOR_DATE": "2026-01-02T10:00:00"}
    subprocess.run(["git", "-C", str(vault), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(vault), "commit", "-qm", "old"], check=True, env=env)
    args = ("query", "resurface", "--today", "2026-10-30", "--limit", "2")
    _, out = run(*args, vault=vault)
    assert [(n["title"], n["linked_from"]) for n in out["notes"]] == [("Hub", 2), ("Side", 1)]  # never superseded
    run(*args, "--limit", "1", "--remember", vault=vault)
    _, again = run(*args, vault=vault)
    assert [n["title"] for n in again["notes"]] == ["Side", "Other"]
    _, recent = run("query", "resurface", "--today", "2026-01-20", vault=vault)
    assert recent["notes"] == []  # changed 18 days earlier


def test_stale_facts_come_oldest_first_and_rotate(run, vault):
    """D128: `(as of D)` stamps older than --days, for the morning's "Still true?" block."""
    notes = vault / "Notes"
    notes.mkdir()
    (notes / "Garden.md").write_text(
        "---\ntype: note\ncreated: 2026-01-01\nsummary: s\n---\n- The plot has 12 beds (as of 2026-03-01).\n"
        "- Water costs 4 per m3 (as of 2026-10-10).\n- `code (as of 2020-01-01)`\n"
    )
    (notes / "Bike.md").write_text(
        "---\ntype: note\ncreated: 2026-01-01\nsummary: s\n---\nTyres changed (as of 2026-05-10).\n"
    )
    (vault / "Daily").mkdir()
    (vault / "Daily" / "2026-01-01.md").write_text("---\ntype: daily\ndate: 2026-01-01\n---\nold (as of 2025-01-01)\n")
    args = ("query", "stale", "--today", "2026-10-30", "--limit", "2")
    _, out = run(*args, vault=vault)
    assert out["count"] == 2  # 2026-10-10 is too recent; code and daily notes don't count
    assert [(f["title"], f["as_of"]) for f in out["facts"]] == [("Garden", "2026-03-01"), ("Bike", "2026-05-10")]
    assert out["facts"][0]["fact"] == "The plot has 12 beds (as of 2026-03-01)."
    run(*args, "--limit", "1", "--remember", vault=vault)
    _, rotated = run(*args, vault=vault)
    assert [f["title"] for f in rotated["facts"]] == ["Bike"]  # asked about yesterday's fact? not again for 14 days


def test_one_to_one_meetings_get_their_own_template(run, work_vault):
    vault = work_vault
    _, one = run(
        "note",
        "new",
        "--type",
        "meeting",
        "--title",
        "Mikael",
        "--field",
        "kind=1-1",
        "--field",
        "date=2026-10-14",
        "--field",
        "summary=s",
        vault=vault,
    )
    _, team = run(
        "note",
        "new",
        "--type",
        "meeting",
        "--title",
        "Planning",
        "--field",
        "kind=team",
        "--field",
        "date=2026-10-14",
        "--field",
        "summary=s",
        vault=vault,
    )
    assert "## Talking points" in (vault / one["rel"]).read_text()
    assert "## Agenda" in (vault / team["rel"]).read_text()


def test_prs_reports_gh_failure_as_json(run, tmp_path):
    code, out = run("prs", "--repo", "o/r", env={"PATH": str(tmp_path)})  # no gh on PATH
    assert code == 1 and out["ok"] is False and "gh failed" in out["error"]


def test_bin_synapsidian_knows_every_script():
    root = Path(__file__).resolve().parents[1] / "plugins" / "synapsidian"
    listed = subprocess.run([str(root / "bin" / "synapsidian"), "help"], capture_output=True, text=True).stderr
    for script in sorted(p.stem for p in (root / "scripts").glob("*.py")):
        if script not in ("approve", "capture"):  # hook-only
            assert script in listed, script
