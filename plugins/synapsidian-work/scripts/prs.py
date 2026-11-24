#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Classify the user's GitHub pull requests for the morning brief (read only, via `gh`).

  prs.py --repo REPOS [--now ISO]                   waiting on me / ready to merge / stuck / in review / drafts
  prs.py --repo REPOS --merged-since ISO            also `merged`: my PRs merged since then (the brief's Done)
  prs.py state owner/name#4792 4794 --repo REPOS    OPEN | MERGED | CLOSED per PR

REPOS is the `github_repos` option: one or more owner/name, as a JSON array or separated by
commas or newlines; `--repo` may also repeat. Every PR in the output carries its `repo`. A bare
number in `state` needs exactly one repository; with several, write it as owner/name#N.

Every "stuck" PR says why, ages count working days (Mon-Fri), and long waits escalate:
a review request open 3+ working days, or my PR red or conflicted for 3+ working days.
Reviews by bots (e.g. coderabbitai) don't count as reviews.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from worklib.dates import now_local, parse_moment, workdays_between
from worklib.options import given_list

FIELDS = "number,title,url,isDraft,createdAt,updatedAt,reviewDecision,mergeable,statusCheckRollup,latestReviews,commits"
FAILED = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING = {"PENDING", "EXPECTED", "QUEUED", "IN_PROGRESS", "WAITING", "REQUESTED"}
ESCALATE_AFTER = 3
NO_REVIEW_AFTER = 2
APPROVED_UNMERGED_AFTER = 2
DRAFT_DAYS = 7


def gh(*args: str) -> Any:
    out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(out.stdout or "null")


def is_bot(login: str) -> bool:
    login = login.lower()
    return login.endswith("[bot]") or login.endswith("bot") or login in {"coderabbitai", "copilot", "github-actions"}


def checks(pr: dict[str, Any]) -> str:
    states = set()
    for check in pr.get("statusCheckRollup") or []:
        states.add(str(check.get("conclusion") or check.get("state") or check.get("status") or "").upper())
    if states & FAILED:
        return "failing"
    if states & PENDING:
        return "pending"
    return "green"


def human_reviews(pr: dict[str, Any]) -> list[dict[str, Any]]:
    return [r for r in pr.get("latestReviews") or [] if not is_bot((r.get("author") or {}).get("login", ""))]


def last_push(pr: dict[str, Any]) -> dt.datetime | None:
    commits = pr.get("commits") or []
    return parse_moment(commits[-1].get("committedDate")) if commits else None


def classify_mine(pr: dict[str, Any], now: dt.datetime) -> dict[str, Any]:
    created = parse_moment(pr.get("createdAt")) or now
    pushed = last_push(pr) or created
    reviews = human_reviews(pr)
    state = checks(pr)
    conflict = pr.get("mergeable") == "CONFLICTING"
    decision = pr.get("reviewDecision") or ""
    approvals = [parse_moment(r.get("submittedAt")) for r in reviews if r.get("state") == "APPROVED"]
    change_requests = [parse_moment(r.get("submittedAt")) for r in reviews if r.get("state") == "CHANGES_REQUESTED"]
    age = workdays_between(created, now)
    reasons: list[str] = []

    if pr.get("isDraft"):
        days = (now - created).days
        if days > DRAFT_DAYS:
            reasons.append(f"draft for {days} days")
        return item(pr, "draft", reasons, age, escalate=False)

    ready = decision == "APPROVED" and state == "green" and not conflict
    if ready:
        approved_at = max((a for a in approvals if a), default=pushed)
        waited = workdays_between(approved_at, now)
        if waited > APPROVED_UNMERGED_AFTER:
            reasons.append(f"approved and green but unmerged for {waited} working days")
        return item(pr, "stuck" if reasons else "ready", reasons, age, escalate=False)

    if decision == "CHANGES_REQUESTED":
        latest_request = max((c for c in change_requests if c), default=None)
        if latest_request is None or pushed <= latest_request:
            reasons.append("changes requested, no push since")
    if state == "failing":
        reasons.append("failing checks")
    if conflict:
        reasons.append("merge conflict")
    if not reviews and age >= NO_REVIEW_AFTER:
        reasons.append(f"no review for {age} working days")

    red_for = workdays_between(pushed, now)
    escalate = (state == "failing" or conflict) and red_for >= ESCALATE_AFTER
    return item(pr, "stuck" if reasons else "in_review", reasons, age, escalate=escalate)


def item(pr: dict[str, Any], group: str, reasons: list[str], age: int, *, escalate: bool) -> dict[str, Any]:
    return {
        "repo": pr.get("repo"),
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "group": group,
        "reasons": reasons,
        "age_workdays": age,
        "escalate": escalate,
    }


def classify(mine: list[dict[str, Any]], requested: list[dict[str, Any]], now: dt.datetime) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {"ready": [], "stuck": [], "in_review": [], "draft": []}
    for pr in mine:
        entry = classify_mine(pr, now)
        groups[entry["group"]].append(entry)
    waiting = []
    for pr in requested:
        if pr.get("isDraft"):
            continue
        age = workdays_between(parse_moment(pr.get("createdAt")) or now, now)
        waiting.append(item(pr, "waiting_on_me", [], age, escalate=age >= ESCALATE_AFTER))
    escalations = [e for e in [*waiting, *groups["stuck"]] if e["escalate"]]
    return {
        "waiting_on_me": sorted(waiting, key=lambda e: -e["age_workdays"]),
        **groups,
        "escalate": escalations,
        "not_checked": ["unanswered review comments"],
    }


def fail(code: int, message: str) -> NoReturn:
    print(json.dumps({"ok": False, "error": message}))
    sys.exit(code)


def pr_ref(ref: str, repos: list[str]) -> tuple[str, str]:
    """`owner/name#123` or a bare `123` (only when one repository is configured) -> (repo, number)."""
    repo, _, number = ref.rpartition("#")
    if not repo:
        if len(repos) != 1:
            fail(2, f"PR {ref}: several repositories are configured; write it as owner/name#{ref}")
        repo = repos[0]
    if not number.isdigit():
        fail(2, f"not a pull request reference: {ref}")
    return repo, number


def open_prs(repo: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # GitHub caps a GraphQL query at 500k nodes; commits + checks per PR blow past it at ~50 PRs.
    base = ["pr", "list", "--repo", repo, "--state", "open", "--json"]
    mine = gh(*base, FIELDS, "--author", "@me", "--limit", "15")
    requested = gh(*base, "number,title,url,isDraft,createdAt", "--search", "review-requested:@me", "--limit", "30")
    return [pr | {"repo": repo} for pr in mine], [pr | {"repo": repo} for pr in requested]


def merged_prs(repo: str, since: dt.datetime) -> list[dict[str, Any]]:
    """My PRs in `repo` merged at or after `since` (GitHub's search is by day; the time is checked here)."""
    found = gh("pr", "list", "--repo", repo, "--state", "merged", "--author", "@me",
               "--search", f"merged:>={since.date().isoformat()}", "--json", "number,title,url,mergedAt",
               "--limit", "30")  # fmt: skip
    return [pr | {"repo": repo} for pr in found]


def merged_since(prs: list[dict[str, Any]], since: dt.datetime) -> list[dict[str, Any]]:
    kept = [pr for pr in prs if (at := parse_moment(pr.get("mergedAt"))) and at >= since]
    return sorted(kept, key=lambda pr: pr["mergedAt"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", nargs="?", default="list", choices=["list", "state"])
    parser.add_argument("refs", nargs="*", help="state: owner/name#N, or N with one repository")
    parser.add_argument("--repo", action="append", help="the github_repos option; may repeat or hold a list")
    parser.add_argument("--now")
    parser.add_argument("--merged-since", help="list: also my PRs merged since this moment (ISO)")
    parser.add_argument("--from-json", help="tests: {'mine': [...], 'requested': [...], 'merged': [...]} instead of gh")
    args = parser.parse_args()
    repos = given_list(args.repo)
    if not repos:
        fail(2, "no GitHub repository: set synapsidian-work's github_repos option")
    since = parse_moment(args.merged_since) if args.merged_since else None
    if args.merged_since and since is None:
        fail(2, f"--merged-since {args.merged_since!r} is not an ISO moment")
    merged: list[dict[str, Any]] = []

    try:
        if args.cmd == "state":
            states = {}
            for ref in args.refs:
                repo, number = pr_ref(ref, repos)
                states[ref] = gh("pr", "view", number, "--repo", repo, "--json", "state").get("state")
            print(json.dumps({"ok": True, "repos": repos, "states": states}))
            return
        mine: list[dict[str, Any]] = []
        requested: list[dict[str, Any]] = []
        if args.from_json:
            data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
            mine = [pr | {"repo": pr.get("repo", repos[0])} for pr in data.get("mine", [])]
            requested = [pr | {"repo": pr.get("repo", repos[0])} for pr in data.get("requested", [])]
            merged = [pr | {"repo": pr.get("repo", repos[0])} for pr in data.get("merged", [])] if since else []
        else:
            for repo in repos:
                repo_mine, repo_requested = open_prs(repo)
                mine += repo_mine
                requested += repo_requested
                merged += merged_prs(repo, since) if since else []
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        fail(1, f"gh failed: {detail.strip()}")
    result = classify(mine, requested, now_local(args.now))
    if since:
        result["merged"] = merged_since(merged, since)
    print(json.dumps({"ok": True, "repos": repos, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
