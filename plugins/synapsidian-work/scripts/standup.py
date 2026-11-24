#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Stand-up arithmetic the skills must not do by hand. Prints JSON, local time.

  standup.py window --days mon,tue,wed,thu,fri --time 10:00 [--now ISO]
      start of the window: the latest stand-up strictly before now
  standup.py cron   --days ... --time ...
      cron line for the scheduled run, an hour before the stand-up
  standup.py repos  --repo '<work_repo_paths>'
      check that each work repository is a local git clone (exit 2 if not)
  standup.py commits --repo '<work_repo_paths>' --since 'YYYY-MM-DD HH:MM'
      the user's own commits in each work repository since the previous stand-up

The skill gets its commits from here rather than from `git` itself: a pre-approved
`git -C * log *` also matches `--output=<file>`, which writes anywhere.

`--days` and `--time` come from the plugin options `standup_days` and `standup_time`;
empty or unsubstituted values fall back to Mon-Fri 10:00.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from worklib.dates import now_local
from worklib.options import given, given_list

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_DAYS = "mon,tue,wed,thu,fri"
DEFAULT_TIME = "10:00"
PREPARE_BEFORE = dt.timedelta(hours=1)


def parse_days(raw: str | None) -> list[int]:
    names = [d.strip().lower() for d in (given(raw) or DEFAULT_DAYS).split(",") if d.strip()]
    if not names or any(n not in WEEKDAYS for n in names):
        raise ValueError(f"stand-up days {raw!r}: use comma-separated names like mon,wed,fri")
    return sorted({WEEKDAYS.index(n) for n in names})


def parse_time(raw: str | None) -> dt.time:
    try:
        return dt.time.fromisoformat(given(raw) or DEFAULT_TIME)
    except ValueError:
        raise ValueError(f"stand-up time {raw!r}: use HH:MM") from None


def last_standup(now: dt.datetime, days: list[int], at: dt.time) -> dt.datetime:
    """The most recent stand-up strictly before `now` (run an hour early on Wednesday -> Tuesday's)."""
    for back in range(8):
        day = (now - dt.timedelta(days=back)).date()
        moment = dt.datetime.combine(day, at, tzinfo=now.tzinfo)
        if day.weekday() in days and moment < now:
            return moment
    raise AssertionError("a stand-up happens every week")


def cron(days: list[int], at: dt.time) -> str:
    start = dt.datetime.combine(dt.date(2000, 1, 3), at)  # a Monday
    run = start - PREPARE_BEFORE
    shift = (run.date() - start.date()).days  # -1 when preparing rolls back past midnight
    cron_days = sorted({((d + shift) % 7 + 1) % 7 for d in days})  # cron: 0 = Sunday, 1 = Monday
    return f"{run.minute} {run.hour} * * {','.join(map(str, cron_days))}"


def repos(raws: list[str] | None) -> dict[str, object]:
    """The work repositories the stand-up reads `git log` from: each must be a local git clone."""
    paths = [Path(raw).expanduser() for raw in given_list(raws)]
    if not paths:
        return {"ok": False, "error": "no work repository: set synapsidian-work's work_repo_paths option"}
    if missing := [str(p) for p in paths if not (p / ".git").exists()]:
        return {"ok": False, "error": f"not a git repository: {', '.join(missing)}; fix the work_repo_paths option"}
    return {"ok": True, "repos": [str(p) for p in paths]}


# A work repository's own .git/config can name programs git runs even on reads (core.fsmonitor).
SAFE_GIT = ("git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat")


def git(repo: str, *args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0"}
    proc = subprocess.run([*SAFE_GIT, "-C", repo, *args], capture_output=True, text=True, check=False, env=env)
    return proc.stdout if proc.returncode == 0 else ""


def commits(raws: list[str] | None, since: str) -> dict[str, object]:
    """The user's commits (by the repository's `user.email`) since `since`, newest first, per repository."""
    checked = repos(raws)
    if not checked["ok"]:
        return checked
    found = []
    for repo in checked["repos"]:  # type: ignore[union-attr]
        email = git(repo, "config", "user.email").strip()
        if not email:
            continue
        out = git(
            repo,
            "log",
            "--no-ext-diff",
            "--no-merges",
            f"--author={email}",
            f"--since={since}",
            "--format=%h%x09%cs%x09%s",
        )
        for line in out.splitlines():
            sha, date, subject = [*line.split("\t", 2), "", ""][:3]
            found.append({"repo": repo, "commit": sha, "date": date, "subject": subject})
    return {"ok": True, "commits": found}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["window", "cron", "repos", "commits"])
    parser.add_argument("--days")
    parser.add_argument("--time")
    parser.add_argument("--now", help="override the current moment (ISO, local if no offset)")
    parser.add_argument("--repo", action="append", help="repos: the work_repo_paths option; may repeat or hold a list")
    parser.add_argument("--since", help="commits: the window's start_local")
    args = parser.parse_args()
    if args.cmd in ("repos", "commits"):
        if args.cmd == "commits" and not (args.since or "").strip():
            print(json.dumps({"ok": False, "error": "commits needs --since"}))
            sys.exit(2)
        result = repos(args.repo) if args.cmd == "repos" else commits(args.repo, args.since)
        print(json.dumps(result))
        sys.exit(0 if result["ok"] else 2)
    try:
        days, at = parse_days(args.days), parse_time(args.time)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(2)

    match args.cmd:
        case "window":
            start = last_standup(now_local(args.now), days, at)
            result = {"start": start.isoformat(timespec="minutes"), "start_local": f"{start:%Y-%m-%d %H:%M}"}
        case "cron":
            result = {"cron": cron(days, at), "days": [WEEKDAYS[d] for d in days], "time": f"{at:%H:%M}"}
    print(json.dumps({"ok": True, **result}))


if __name__ == "__main__":
    main()
