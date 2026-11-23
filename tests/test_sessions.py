from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "synapsidian"
UTC = {"TZ": "UTC"}


def user(ts: str, text: str, **extra: object) -> dict:
    return {
        "type": "user",
        "timestamp": ts,
        "origin": {"kind": "human"},
        "cwd": "/work/repo",
        "gitBranch": "feat/x",
        "message": {"content": text},
        **extra,
    }


def tool(ts: str, name: str, **tool_input: object) -> dict:
    return {
        "type": "assistant",
        "timestamp": ts,
        "cwd": "/work/repo",
        "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]},
    }


def said(ts: str, text: str) -> dict:
    return {"type": "assistant", "timestamp": ts, "message": {"content": [{"type": "text", "text": text}]}}


def write_transcript(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def setup(vault: Path, tmp_path: Path):
    """A vault with a queue holding one session that spans two days, plus a scheduled run."""
    projects = tmp_path / "projects"
    two_days = write_transcript(
        projects / "p" / "sess-a.jsonl",
        [
            {"type": "ai-title", "aiTitle": "Export fix"},
            user("2026-10-12T09:00:00Z", "fix the export rounding <system-reminder>noise</system-reminder>"),
            tool("2026-10-12T09:05:00Z", "Edit", file_path="/work/repo/src/export.ts"),
            tool("2026-10-12T09:06:00Z", "Bash", command="cd x\ngit commit -m 'fix rounding'\nls"),
            {"type": "pr-link", "url": "https://github.com/o/r/pull/7"},
            user("2026-10-13T10:00:00Z", "now add a test"),
            tool("2026-10-13T10:05:00Z", "Write", file_path="/work/repo/src/export.test.ts"),
            said("2026-10-13T10:06:00Z", "Added the regression test."),
            user("2026-10-13T10:07:00Z", "subagent prompt", isSidechain=True),
        ],
    )
    scheduled = write_transcript(
        projects / "p" / "sess-b.jsonl",
        [
            user("2026-10-13T18:00:00Z", '<scheduled-task name="synapsidian-evening">run</scheduled-task>'),
        ],
    )
    state = vault / ".git" / "synapsidian"
    state.mkdir(parents=True, exist_ok=True)
    rows = [
        {"session_id": "sess-a", "date": "2026-10-12", "transcript_path": str(two_days)},
        {"session_id": "sess-a", "date": "2026-10-13", "transcript_path": str(two_days)},
        {"session_id": "sess-b", "date": "2026-10-13", "transcript_path": str(scheduled)},
        {"session_id": "sess-gone", "date": "2026-10-13", "transcript_path": str(tmp_path / "missing.jsonl")},
    ]
    (state / "session-queue.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    return {"projects": projects, "state": state}


def test_digest_keeps_only_that_days_records(run, vault, setup):
    _, out = run("sessions", "digest", "--date", "2026-10-12", vault=vault, env=UTC)
    assert "### Export fix" in out and "- fix the export rounding" in out
    assert "noise" not in out and "now add a test" not in out
    assert "- src/export.ts" in out and "- git commit -m 'fix rounding'" in out and "- ls" not in out
    assert "PRs: https://github.com/o/r/pull/7" in out
    assert "with work (mark after writing): sess-a" in out


def test_sessions_off_the_record_never_reach_a_digest(run, vault, setup):
    """D123: an excluded folder or #off-the-record keeps a whole session out; <private> spans go."""
    projects = setup["projects"]
    write_transcript(
        projects / "p" / "sess-c.jsonl",
        [user("2026-10-12T11:00:00Z", "plan the release <private>salary is 1234</private> today")],
    )
    write_transcript(
        projects / "p" / "sess-d.jsonl",
        [user("2026-10-12T12:00:00Z", "#off-the-record help me with a letter to my doctor")],
    )
    queue = setup["state"] / "session-queue.jsonl"
    rows = [{"session_id": s, "date": "2026-10-12", "transcript_path": str(projects / "p" / f"{s}.jsonl")}
            for s in ("sess-c", "sess-d")]  # fmt: skip
    queue.write_text(queue.read_text() + "".join(json.dumps(r) + "\n" for r in rows))

    _, out = run("sessions", "digest", "--date", "2026-10-12", vault=vault, env=UTC)
    assert "- plan the release today" in out.replace("  ", " ") and "1234" not in out
    assert "doctor" not in out and "sess-d" in out.split("no work worth logging (mark too):")[1]

    _, out = run(
        "sessions",
        "digest",
        "--date",
        "2026-10-12",
        vault=vault,
        env={**UTC, "CLAUDE_PLUGIN_OPTION_SESSION_EXCLUDE_PATHS": '["/work"]'},
    )
    assert "fix the export rounding" not in out and "- plan the release" not in out  # every /work/... session
    assert "sess-a" in out.split("no work worth logging (mark too):")[1]


def test_auto_memory_changes_are_listed_once_and_off_the_record_folders_stay_out(run, vault, setup):
    """D136: Claude Code's memory files as an evening source; marked versions aren't listed again."""
    projects = setup["projects"]
    work = projects / "-work-repo" / "memory"
    private = projects / "-home-me-Clients-acme" / "memory"
    work.mkdir(parents=True)
    private.mkdir(parents=True)
    (work / "MEMORY.md").write_text("- Run tests with pnpm vitest <private>token x</private>\n")
    (private / "MEMORY.md").write_text("- Client secret plans\n")
    env = {"CLAUDE_PLUGIN_OPTION_SESSION_EXCLUDE_PATHS": "/home/me/Clients"}
    _, out = run("sessions", "memory", vault=vault, env=env)
    assert "-work-repo / MEMORY.md" in out and "pnpm vitest" in out and "token x" not in out
    assert "Client secret" not in out
    marks = out.split("mark with: synapsidian sessions memory-mark ")[1].strip().replace("'", "").split()
    run("sessions", "memory-mark", *marks, vault=vault, env=env)
    _, again = run("sessions", "memory", vault=vault, env=env)
    assert "Nothing changed." in again
    (work / "MEMORY.md").write_text("- Run tests with pnpm vitest\n- Use the design tokens\n")
    _, changed = run("sessions", "memory", vault=vault, env=env)
    assert "design tokens" in changed


def test_digests_print_no_credentials(run, vault, setup):
    """D158: the evening run writes notes from the digest, so a token is blanked before any cut."""
    token = "ghp_" + "a" * 36
    write_transcript(
        setup["projects"] / "p" / "sess-a.jsonl",
        [
            # The token straddles the prompt's 300-character cut: cut first, half of it would stay.
            user("2026-10-12T09:00:00Z", "x " * 140 + f"use {token} for the API"),
            tool("2026-10-12T09:05:00Z", "Bash", command=f"git push https://{token}@example.com/o/r"),
            said("2026-10-12T09:06:00Z", f"Pushed with {token}."),
        ],
    )
    _, out = run("sessions", "digest", "--date", "2026-10-12", vault=vault, env=UTC)
    assert "ghp_" not in out and "Pushed with [redacted: GitHub token]." in out
    assert "- git push https://[redacted: GitHub token]@example.com/o/r" in out

    memory = setup["projects"] / "-work-repo" / "memory"
    memory.mkdir(parents=True)
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    (memory / "MEMORY.md").write_text(f"- Deploy key:\n{key}\n- Run tests with pnpm vitest\n")
    _, listed = run("sessions", "memory", vault=vault)
    assert "MIIEow" not in listed and "[redacted: private key]" in listed and "pnpm vitest" in listed


def test_resumed_session_is_logged_on_each_day(run, vault, setup):
    run("sessions", "mark", "--date", "2026-10-12", "sess-a", vault=vault, env=UTC)
    _, pending = run("sessions", "pending", vault=vault, env=UTC)
    assert pending["days"] == {"2026-10-13": ["sess-a", "sess-b", "sess-gone"]}  # the old harvester lost sess-a here

    _, out = run("sessions", "digest", "--date", "2026-10-13", vault=vault, env=UTC)
    assert "- now add a test" in out and "subagent prompt" not in out
    assert "closing message: Added the regression test." in out
    assert "no work worth logging (mark too): sess-b" in out  # scheduled runs aren't work
    assert "transcript missing (mark too): sess-gone" in out


def test_work_before_a_save_is_skipped(run, vault, setup):
    saved = {"session_id": "sess-a", "saved_at": "2026-10-13T10:01:00+00:00"}
    (setup["state"] / "saved-sessions.jsonl").write_text(json.dumps(saved) + "\n")
    _, out = run("sessions", "digest", "--date", "2026-10-13", vault=vault, env=UTC)
    assert "now add a test" not in out  # 10:00, before the save
    assert "export.test.ts" in out  # 10:05, after it


def test_mark_is_idempotent(run, vault, setup):
    _, first = run("sessions", "mark", "--date", "2026-10-13", "sess-b", "sess-b", vault=vault, env=UTC)
    _, again = run("sessions", "mark", "--date", "2026-10-13", "sess-b", vault=vault, env=UTC)
    assert (first["marked"], again["marked"], again["already_marked"]) == (1, 0, 1)


def test_session_queued_only_when_it_ended_is_logged_on_every_day_it_was_used(run, vault, setup, tmp_path):
    """A desktop session resumed across days ends once; its queue row carries only the last day."""
    long_one = write_transcript(
        setup["projects"] / "p" / "sess-long.jsonl",
        [user("2026-10-12T15:00:00Z", "start the architect notes"), user("2026-10-13T09:00:00Z", "finish them")],
    )
    row = {"session_id": "sess-long", "date": "2026-10-13", "transcript_path": str(long_one)}
    with (setup["state"] / "session-queue.jsonl").open("a") as handle:
        handle.write(json.dumps(row) + "\n")
    _, pending = run("sessions", "pending", vault=vault, env=UTC)
    assert "sess-long" in pending["days"]["2026-10-12"] and "sess-long" in pending["days"]["2026-10-13"]


def test_work_after_a_mark_is_pending_again_and_only_it_is_digested(run, vault, setup):
    """2026-10-13: a session marked at 17:36 kept working until 22:24; that work was lost."""
    code, marked = run(
        "sessions", "mark", "--date", "2026-10-13", "--until", "2026-10-13T10:04:00Z", "sess-a", vault=vault, env=UTC
    )
    assert code == 0 and marked["marked"] == 1
    _, out = run("sessions", "digest", "--date", "2026-10-13", vault=vault, env=UTC)
    assert "sess-a" in out.split("with work (mark after writing):")[1].splitlines()[0]  # the 10:05 edit is after it
    assert "now add a test" not in out and "export.test.ts" in out

    run("sessions", "mark", "--date", "2026-10-13", "sess-a", vault=vault, env=UTC)  # now: covers everything
    _, pending = run("sessions", "pending", vault=vault, env=UTC)
    assert "sess-a" not in pending["days"].get("2026-10-13", [])
    _, again = run("sessions", "mark", "--date", "2026-10-13", "sess-a", vault=vault, env=UTC)
    assert again["marked"] == 0 and again["already_marked"] == 1  # nothing new: no extra row


def test_open_session_never_queued_is_found_by_scanning(run, vault, setup):
    write_transcript(
        setup["projects"] / "q" / "sess-open.jsonl",
        [user("2026-10-13T12:00:00Z", "still working"), tool("2026-10-13T12:05:00Z", "Edit", file_path="/w/a.ts")],
    )
    write_transcript(setup["projects"] / "q" / "sess-old.jsonl", [user("2026-10-01T12:00:00Z", "before synapsidian")])
    _, pending = run("sessions", "pending", vault=vault, env=UTC)
    assert "sess-open" in pending["days"]["2026-10-13"]
    assert "2026-10-01" not in pending["days"]  # before the first queued day: not synapsidian's to log
    _, out = run("sessions", "digest", "--date", "2026-10-13", vault=vault, env=UTC)
    assert "- still working" in out and "mark with: --date 2026-10-13 --until " in out


def test_closing_message_headings_dont_look_like_sessions(run, vault, setup):
    write_transcript(
        setup["projects"] / "q" / "sess-h.jsonl",
        [user("2026-10-13T12:00:00Z", "explain"), said("2026-10-13T12:01:00Z", "Done.\n\n## Why\n\n### Details\nok")],
    )
    _, out = run("sessions", "digest", "--date", "2026-10-13", vault=vault, env=UTC)
    assert "closing message: Done. ## Why ### Details ok" in out
    assert not any(line.startswith(("## Why", "### Details")) for line in out.splitlines())


def test_since_scan_reads_open_sessions_by_timestamp(run, vault, setup):
    env = {**UTC, "SYNAPSIDIAN_PROJECTS_DIR": str(setup["projects"])}
    _, out = run("sessions", "digest", "--since", "2026-10-13 00:00", "--scan", vault=vault, env=env)
    assert "now add a test" in out and "fix the export rounding" not in out
    assert "with work (mark" not in out  # nothing to mark in a stand-up scan


@pytest.mark.parametrize(
    ("day", "kind", "period_start"),
    [
        ("2026-10-16", "week", "2026-10-12"),
        ("2026-10-30", "month", "2026-10-01"),
        ("2026-12-25", "quarter", "2026-10-01"),
    ],
)
def test_review_kind(run, day, kind, period_start):
    _, result = run("when", "review", "--date", day)
    assert (result["kind"], result["period_start"]) == (kind, period_start)


def test_a_missed_friday_review_fired_later_reviews_that_friday(run, vault):
    """D121: a Friday review that ran on Monday used to be a Monday-to-Monday week, and a
    month's or quarter's review was lost."""
    _, monday = run("when", "review", "--now", "2026-11-02T09:00", vault=vault)
    assert monday == {"ok": True, "kind": "month", "period_start": "2026-10-01", "period_end": "2026-10-30",
                      "catch_up_for": "2026-10-30"}  # fmt: skip
    assert run("when", "review", "--now", "2026-10-31T10:00", vault=vault)[1]["catch_up_for"] == "2026-10-30"

    (vault / "Reviews").mkdir()
    (vault / "Reviews" / "2026-10-30 month.md").write_text(
        "---\ntype: review\ncreated: 2026-10-30\nsummary: s\nperiod: month\nperiod_start: 2026-10-01\n"
        "period_end: 2026-10-30\n---\n"
    )
    _, after = run("when", "review", "--now", "2026-11-02T09:00", vault=vault)
    assert "catch_up_for" not in after and after["period_end"] == "2026-11-02"  # asked for on Monday itself
    _, midweek = run("when", "review", "--now", "2026-11-04T09:00")
    assert midweek["period_start"] == "2026-11-02" and "catch_up_for" not in midweek


def test_done_window_starts_at_the_previous_morning_run(run, vault):
    """D129: "Done" counts from the last morning brief, wherever its commit is."""
    import os

    (vault / "a.md").write_text("a")
    env = {
        **os.environ,
        "GIT_COMMITTER_DATE": "2026-10-29T08:31:00+01:00",
        "GIT_AUTHOR_DATE": "2026-10-29T08:31:00+01:00",
    }
    subprocess.run(["git", "-C", str(vault), "add", "a.md"], check=True)
    subprocess.run(["git", "-C", str(vault), "commit", "-qm", "synapsidian(morning): brief"], check=True, env=env)
    _, out = run("when", "done-window", "--now", "2026-10-30T09:00+01:00", vault=vault, env={"TZ": "Europe/Warsaw"})
    assert out["start_local"] == "2026-10-29 08:31"
    (vault / ".git" / "synapsidian").mkdir(exist_ok=True)
    (vault / ".git" / "synapsidian" / "swept-commits.jsonl").write_text(
        '{"skill": "morning", "at": "2026-10-30T07:45:00+01:00", "files": ["Daily/x.md"], "shas": ["abc"]}\n'
    )
    _, out = run("when", "done-window", "--now", "2026-10-31T09:00+01:00", vault=vault, env={"TZ": "Europe/Warsaw"})
    assert out["start_local"] == "2026-10-30 07:45"  # a run Obsidian Git committed first still counts
    _, late = run("when", "done-window", "--now", "2026-11-10T09:00+01:00", vault=vault, env={"TZ": "Europe/Warsaw"})
    assert late["start_local"] == "2026-11-09 07:00"  # none for days: 26 hours back


def test_done_window_and_workdays(run):
    assert run("when", "done-window", "--now", "2026-10-12T09:05")[1]["start_local"] == "2026-10-09 09:00"
    # The clocks went back on Sunday 2026-10-25: Friday 09:00 was still summer time (+02:00).
    _, out = run("when", "done-window", "--now", "2026-10-26T09:00", env={"TZ": "Europe/Warsaw"})
    assert out["start"] == "2026-10-23T09:00+02:00" and out["start_local"] == "2026-10-23 09:00"
    assert run("when", "done-window", "--now", "2026-10-14T09:05")[1]["start_local"] == "2026-10-13 07:05"
    assert run("when", "workdays", "--from", "2026-10-09T10:00", "--now", "2026-10-13T10:00")[1]["workdays"] == 2


def test_session_end_hook_queues_without_uv(vault, tmp_path):
    payload = {"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": "/work", "reason": "prompt_input_exit"}
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_PLUGIN_OPTION_VAULT_PATH": str(vault)}
    proc = subprocess.run(
        [str(ROOT / "hooks" / "session-end.sh")], input=json.dumps(payload), text=True, env=env, capture_output=True
    )
    assert proc.returncode == 0
    row = json.loads((vault / ".git" / "synapsidian" / "session-queue.jsonl").read_text().splitlines()[0])
    assert (row["session_id"], row["transcript_path"], row["reason"]) == ("s1", "/t/s1.jsonl", "prompt_input_exit")


@pytest.mark.parametrize("spelling", ["$HOME/Synapsidian", "${HOME}/Synapsidian", "~/Synapsidian"])
def test_session_end_hook_expands_home_like_the_scripts(vault, spelling):
    """D129: a vault path written with $HOME was queued by the scripts' config but not by the hook."""
    payload = {"session_id": "s2", "transcript_path": "/t/s2.jsonl", "cwd": "/work"}
    env = {"PATH": "/usr/bin:/bin", "HOME": str(vault.parent), "SYNAPSIDIAN_VAULT": spelling}
    subprocess.run([str(ROOT / "hooks" / "session-end.sh")], input=json.dumps(payload), text=True, env=env, check=True)
    assert '"s2"' in (vault / ".git" / "synapsidian" / "session-queue.jsonl").read_text()


def test_session_end_hook_reads_saved_option_and_ignores_unset_vault(vault, tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"pluginConfigs": {"synapsidian@x": {"options": {"vault_path": str(vault)}}}}))
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    hook = str(ROOT / "hooks" / "session-end.sh")
    subprocess.run([hook], input='{"session_id": "s2"}', text=True, env=env, check=True)
    assert "s2" in (vault / ".git" / "synapsidian" / "session-queue.jsonl").read_text()

    empty_home = tmp_path / "nohome"
    empty_home.mkdir()
    proc = subprocess.run(
        [hook], input='{"session_id": "s3"}', text=True, env={"PATH": "/usr/bin:/bin", "HOME": str(empty_home)}
    )
    assert proc.returncode == 0
