#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Commit the files one skill run touched, as one commit: `synapsidian(<skill>): <message>`.

  commit.py --vault V --data-dir D --skill save --message "decision on export format" FILE...

FILEs are vault-relative. Never stages anything else, never pushes.

`broken_links` in the result lists the [[links]] this commit added to those notes that
resolve to no file (`rel`, `link`). It is a report, never a refusal (D43): the commit is made
either way, and a fix goes in a second commit. Sources/ and Archive/ are not checked.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from synapsidianlib import config, gitops, links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vault")
    parser.add_argument("--data-dir")
    parser.add_argument("--skill", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--record-session", metavar="SESSION_ID", help="note this Claude session as saved, so the evening run skips it"
    )
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()

    vault_root = config.write_vault(args.vault)
    if vault_root is None or not gitops.is_repo(vault_root):
        print(json.dumps({"ok": False, "error": "vault is not a git repository; run /synapsidian:setup"}))
        sys.exit(2)

    message = f"synapsidian({args.skill}): {' '.join(args.message.split())}"
    state = config.state_dir(vault_root, args.data_dir)
    # Before the commit, while HEAD still holds each note as it was. A check that fails must
    # never cost the run its commit.
    try:
        broken = links.new_unresolved(vault_root, args.files)
    except Exception:
        broken = []
    try:
        with gitops.vault_lock(state, args.timeout):
            result = gitops.commit(vault_root, args.files, message)
            sha = result.sha
            if args.record_session and not args.record_session.startswith("${"):
                record = {
                    "session_id": args.record_session,
                    "skill": args.skill,
                    "sha": sha,
                    "saved_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                }
                with (state / "saved-sessions.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record) + "\n")
            if result.swept:
                # The run's work sits in someone else's commit (Obsidian Git, D85): note it, so
                # `query commits` (the morning's overnight list) still sees this run (D129).
                swept = {
                    "skill": args.skill,
                    "message": message,
                    "files": [s["path"] for s in result.swept],
                    "shas": sorted({s["sha"] for s in result.swept}),
                    "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                with (state / gitops.SWEPT_LOG).open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(swept, ensure_ascii=False) + "\n")
    except gitops.LockTimeout as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(4)
    except Exception as exc:  # git failures: report, don't traceback into the transcript
        stderr = getattr(exc, "stderr", "") or str(exc)
        print(json.dumps({"ok": False, "error": stderr.strip()}))
        sys.exit(1)
    report: dict[str, object] = {
        "ok": True,
        "sha": sha,
        "message": message if sha else None,
        "committed": sha is not None,
    }
    if broken:
        report["broken_links"] = broken
    if result.archive_sources:
        report["added_archive_sources"] = result.archive_sources
    if result.swept:
        report["swept"] = result.swept
        report["warning"] = (
            f"{len(result.swept)} listed file(s) were already committed by another commit "
            "(usually Obsidian Git's auto-commit); this run's changes to them are in that commit, not in this one"
        )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
