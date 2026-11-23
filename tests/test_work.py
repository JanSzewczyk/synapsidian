"""synapsidian-work's own scripts: options arrive as arguments, empty or unsubstituted means off."""

from __future__ import annotations

import subprocess

import pytest

from conftest import WORK
from synapsidianlib import frontmatter


@pytest.mark.parametrize(
    ("now", "start"),
    [
        ("2026-10-14T11:00", "2026-10-13 12:00"),  # Wednesday morning -> Tuesday
        ("2026-10-13T11:00", "2026-10-08 12:00"),  # Tuesday morning -> last Thursday
        ("2026-10-15T13:00", "2026-10-15 12:00"),  # Thursday after the stand-up -> today's
    ],
)
def test_standup_window_follows_the_configured_days(run, now, start):
    code, out = run("standup", "window", "--days", "tue,wed,thu", "--time", "12:00", "--now", now)
    assert code == 0 and out["start_local"] == start


def test_standup_defaults_to_weekdays_when_options_are_unset(run):
    _, out = run(
        "standup", "window", "--days", "${user_config.standup_days}", "--time", "", "--now", "2026-10-13T09:00"
    )
    assert out["start_local"] == "2026-10-12 10:00"  # Monday 10:00, the default


@pytest.mark.parametrize(
    ("days", "time", "cron"),
    [("tue,wed,thu", "12:00", "0 11 * * 2,3,4"), ("mon,fri", "09:30", "30 8 * * 1,5"), ("mon", "00:30", "30 23 * * 0")],
)
def test_standup_cron_runs_an_hour_early(run, days, time, cron):
    assert run("standup", "cron", "--days", days, "--time", time)[1]["cron"] == cron


def test_bad_standup_days_are_refused(run):
    code, out = run("standup", "window", "--days", "monday-ish", "--time", "10:00")
    assert code == 2 and "days" in out["error"]


@pytest.mark.parametrize("repo", [None, "", "${user_config.github_repos}", "[]"])
def test_prs_needs_a_repository(run, repo):
    code, out = run("prs", *(["--repo", repo] if repo is not None else []))
    assert code == 2 and "github_repos" in out["error"]


@pytest.mark.parametrize(
    "raw",
    ['["acme/web", "acme/api"]', "acme/web, acme/api", "acme/web\nacme/api\nacme/web", "acme/web,,acme/api,"],
)
def test_prs_reads_every_spelling_of_a_repository_list(run, tmp_path, raw):
    fixture = tmp_path / "prs.json"
    fixture.write_text('{"mine": [], "requested": []}', encoding="utf-8")
    code, out = run("prs", "--repo", raw, "--from-json", str(fixture), "--now", "2026-10-14T09:00")
    assert code == 0 and out["repos"] == ["acme/web", "acme/api"]


def test_prs_lists_what_merged_since_the_done_window(run, tmp_path):
    """The brief's Done section asked for merged PRs that `prs` never returned (D121)."""
    fixture = tmp_path / "prs.json"
    fixture.write_text(
        '{"mine": [], "requested": [], "merged": ['
        '{"number": 1, "title": "Old", "url": "u1", "mergedAt": "2026-10-12T15:00:00Z"},'
        '{"number": 2, "title": "New", "url": "u2", "mergedAt": "2026-10-13T08:30:00Z"}]}',
        encoding="utf-8",
    )
    args = ("prs", "--repo", "acme/web", "--from-json", str(fixture), "--now", "2026-10-14T09:00")
    _, out = run(*args, "--merged-since", "2026-10-13T07:00:00+00:00")
    assert [pr["number"] for pr in out["merged"]] == [2] and out["merged"][0]["repo"] == "acme/web"
    assert "merged" not in run(*args)[1]
    assert run(*args, "--merged-since", "yesterday")[0] == 2


def test_standup_commits_come_from_the_script_with_the_repositorys_own_email(run, tmp_path):
    repo = tmp_path / "front"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "me@example.com"], check=True)
    subprocess.run([*git, "config", "user.name", "Me"], check=True)
    for who, msg in (("me@example.com", "mine"), ("you@example.com", "theirs")):
        (repo / msg).write_text(msg)
        subprocess.run([*git, "add", msg], check=True)
        subprocess.run([*git, "-c", f"user.email={who}", "commit", "-qm", msg], check=True)
    code, out = run("standup", "commits", "--repo", str(repo), "--since", "2000-01-01 00:00")
    assert code == 0 and [c["subject"] for c in out["commits"]] == ["mine"]
    assert run("standup", "commits", "--repo", str(repo))[0] == 2  # --since is required


def test_prs_state_needs_the_repository_when_several_are_configured(run):
    code, out = run("prs", "state", "123", "--repo", "acme/web,acme/api")
    assert code == 2 and "owner/name#123" in out["error"]


def test_standup_repos_needs_a_repository(run):
    code, out = run("standup", "repos", "--repo", "${user_config.work_repo_paths}")
    assert code == 2 and "work_repo_paths" in out["error"]


def test_standup_repos_reads_every_spelling_of_the_list(run, tmp_path):
    front, admin = tmp_path / "front", tmp_path / "admin"
    for clone in (front, admin):
        (clone / ".git").mkdir(parents=True)
    code, out = run("standup", "repos", "--repo", f'["{front}", "{admin}"]')
    assert code == 0 and out["repos"] == [str(front), str(admin)]
    assert run("standup", "repos", "--repo", f"{front},{admin}")[1] == out


def test_standup_repos_refuses_a_path_that_is_not_a_repository(run, tmp_path):
    code, out = run("standup", "repos", "--repo", str(tmp_path))
    assert code == 2 and "not a git repository" in out["error"]


def new_note(run, vault, note_type, title, **fields):
    args = [arg for key, value in fields.items() for arg in ("--field", f"{key}={value}")]
    return run("note", "new", "--type", note_type, "--title", title, *args, vault=vault)


def test_a_win_lands_in_wins_with_its_sections_and_only_known_impacts(run, work_vault):
    code, out = new_note(
        run, work_vault, "win", "Export ships a week early",
        date="2026-10-20", evidence="[[T12 Fix the export]],https://example.com/pr/123", summary="s",
    )  # fmt: skip
    assert code == 0 and out["rel"] == "Wins/2026-10-20 Export ships a week early.md", out
    note = frontmatter.parse((work_vault / out["rel"]).read_text())
    assert note.meta["impact"] == "medium"  # the default
    assert note.meta["evidence"] == ["[[T12 Fix the export]]", "https://example.com/pr/123"]
    assert [line for line in note.body.splitlines() if line.startswith("## ")] == [
        "## What", "## Impact", "## Evidence", "## Who saw it",
    ]  # fmt: skip
    code, out = new_note(run, work_vault, "win", "Huge", date="2026-10-21", impact="huge", summary="s")
    assert code == 2 and "impact" in out["error"]


def test_wins_of_a_period_come_from_one_query(run, work_vault):
    for day in ("2026-09-30", "2026-10-02", "2026-10-31"):
        new_note(run, work_vault, "win", f"Win {day}", date=day, summary="s")
    _, out = run("query", "notes", "--type", "win", "--where", "date>=2026-10-01", "--where", "date<=2026-10-30",
                 vault=work_vault)  # fmt: skip
    assert [n["title"] for n in out["notes"]] == ["2026-10-02 Win 2026-10-02"]


def test_a_retro_meeting_gets_the_retro_sections(run, work_vault):
    code, out = new_note(run, work_vault, "meeting", "Sprint 42", kind="retro", date="2026-10-28", summary="s")
    assert code == 0 and out["rel"] == "Meetings/2026-10-28 retro Sprint 42.md", out
    headings = [line for line in (work_vault / out["rel"]).read_text().splitlines() if line.startswith("## ")]
    assert headings == [
        "## Agenda", "## Went well", "## Didn't go well", "## Ideas", "## Notes", "## Decisions", "## Action items",
    ]  # fmt: skip


def test_hooks_print_their_reference_and_retro_is_matched_before_review():
    def hook(name: str) -> str:
        proc = subprocess.run([str(WORK / "bin" / "synapsidian-work"), "hook", name], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return proc.stdout

    review = hook("review")
    assert "## Listing wins" in review and "--type win" in review and "--before Decisions" in review
    meetings = hook("meetings")
    assert "`retro`" in meetings and "before synapsidian's own" in meetings
    assert subprocess.run([str(WORK / "bin" / "synapsidian-work"), "hook", "nope"], capture_output=True).returncode == 2
