#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.2"]
# ///
"""Calendar arithmetic the skills must not do by hand. Prints JSON, local time.

when.py done-window [--now ISO]   morning brief "Done" start: the previous morning run; without
                                  one, 26 h back, or Friday 09:00 on Mondays
when.py review      [--date D]    week / month / quarter for that day, with the period's bounds;
                                  without --date, a run after a Friday that has no review yet
                                  is that Friday's catch-up (`catch_up_for`)
when.py workdays --from ISO [--now ISO]   working days (Mon-Fri) elapsed between two moments
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from synapsidianlib import config, gitops, schema, vault
from synapsidianlib.dates import now_local, workdays_between

MORNING_TIME = dt.time(9, 0)
LAST_MORNING_MAX_DAYS = 4  # a long weekend; an older morning run means the brief didn't run for a while


def last_morning(vault_root: Path | None, today: dt.date) -> dt.datetime | None:
    """When the latest morning run before today committed: its `synapsidian(morning)` commit, or the
    run Obsidian Git swept (D85, logged by `synapsidian commit`)."""
    if vault_root is None or not gitops.is_repo(vault_root):
        return None
    floor = today - dt.timedelta(days=LAST_MORNING_MAX_DAYS)
    out = gitops.git(
        vault_root, "log", "--format=%cI", "--grep=^synapsidian(morning)", "-20", check=False
    ).stdout.split()
    found = [dt.datetime.fromisoformat(t).astimezone() for t in out]
    log = config.state_dir(vault_root) / gitops.SWEPT_LOG
    for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
        try:
            row = json.loads(line)
            if row.get("skill") == "morning":
                found.append(dt.datetime.fromisoformat(row["at"]).astimezone())
        except (ValueError, KeyError, TypeError):
            continue
    before = [t for t in found if floor <= t.date() < today]
    return max(before, default=None)


def done_window(now: dt.datetime, vault_root: Path | None = None) -> dt.datetime:
    """Start of the brief's "Done": the previous morning run (D129); without one in the last few
    days, 26 hours back, or Friday 09:00 on a Monday."""
    if previous := last_morning(vault_root, now.date()):
        return previous
    if now.weekday() == 0:  # Monday: everything since Friday morning
        friday = now.date() - dt.timedelta(days=3)
        # Friday's own UTC offset, not Monday's: the clocks may have changed over the weekend.
        return dt.datetime.combine(friday, MORNING_TIME).astimezone()
    return now - dt.timedelta(hours=26)


def is_last_weekday_of_month(day: dt.date) -> bool:
    return (day + dt.timedelta(days=7)).month != day.month


FRIDAY = 4


def last_review_end(vault_root: Path | None) -> dt.date | None:
    """The latest `period_end` among the vault's review notes, archived ones included."""
    if vault_root is None or not vault_root.is_dir():
        return None
    ends = [
        end
        for n in vault.iter_notes(vault_root, include_cold=True)
        if n.type == "review" and (end := schema.as_date(n.get("period_end")))
    ]
    return max(ends, default=None)


def review_day(day: dt.date, last_end: dt.date | None) -> dt.date:
    """The day a review run on `day` is for. The review is scheduled for Fridays and a missed run
    fires at the next launch (D121): on the weekend, or on the Monday while that Friday still
    has no review, the run is the Friday's catch-up. Otherwise it is for `day` itself."""
    friday = day - dt.timedelta(days=(day.weekday() - FRIDAY) % 7)
    if day.weekday() > FRIDAY:
        return friday
    if (day - friday).days == 3 and (last_end is None or last_end < friday):
        return friday
    return day


def review(day: dt.date) -> dict[str, str]:
    if is_last_weekday_of_month(day) and day.month % 3 == 0:
        kind, start = "quarter", dt.date(day.year, day.month - 2, 1)
    elif is_last_weekday_of_month(day):
        kind, start = "month", day.replace(day=1)
    else:
        kind, start = "week", day - dt.timedelta(days=day.weekday())
    return {"kind": kind, "period_start": start.isoformat(), "period_end": day.isoformat()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", choices=["done-window", "review", "workdays"])
    parser.add_argument("--now", help="override the current moment (ISO, local if no offset)")
    parser.add_argument("--date", help="review: the day to classify (default: today, or a missed Friday)")
    parser.add_argument("--vault", help="the vault whose review notes and morning runs the windows read")
    parser.add_argument("--from", dest="start", help="workdays: start moment (ISO)")
    args = parser.parse_args()
    now = now_local(args.now)

    match args.cmd:
        case "done-window":
            start = done_window(now, config.vault_path(args.vault))
            result = {"start": start.isoformat(timespec="minutes"), "start_local": f"{start:%Y-%m-%d %H:%M}"}
        case "review":
            if args.date:  # an explicit day is taken as asked
                result = review(dt.date.fromisoformat(args.date))
            else:
                day = review_day(now.date(), last_review_end(config.vault_path(args.vault)))
                result = review(day) | ({"catch_up_for": day.isoformat()} if day != now.date() else {})
        case "workdays":
            if not args.start:
                parser.error("workdays needs --from")
            result = {"workdays": workdays_between(now_local(args.start), now)}
    print(json.dumps({"ok": True, **result}))


if __name__ == "__main__":
    main()
