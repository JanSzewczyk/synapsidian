"""Vault commits: one per skill run, only the files that run touched, serialised by a lock."""

from __future__ import annotations

import datetime as dt
import fcntl
import os
import re
import subprocess
import time
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


class LockTimeout(RuntimeError):
    pass


@contextmanager
def vault_lock(data_dir: Path, timeout: float = 60.0, name: str = "vault.lock") -> Iterator[None]:
    """Exclusive lock shared by every synapsidian process writing to the vault: `vault.lock` for
    commits, another name for a separate critical section (task ids, daily-note blocks)."""
    lock_path = data_dir / name
    with lock_path.open("a") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"another synapsidian run held {lock_path} for {timeout:.0f}s") from None
                time.sleep(0.2)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


# Paths synapsidian passes are file names, never patterns: without this, `Notes/Plan [v2].md` would
# also match (and commit) `Notes/Plan 2.md`.
GIT_ENV = {**os.environ, "GIT_LITERAL_PATHSPECS": "1"}


def git(vault: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=check, env=GIT_ENV)


def is_repo(vault: Path) -> bool:
    return git(vault, "rev-parse", "--is-inside-work-tree", check=False).returncode == 0


def last_commit_dates(vault: Path, folders: Sequence[str]) -> dict[str, dt.date]:
    """Vault-relative path -> date of the latest commit that touched it, from one `git log` walk.

    Dates a note's last change better than mtime, which a clone or a sync resets.
    """
    out = git(vault, "log", "--format=%x00%cs", "--name-only", "-z", "--", *folders, check=False)
    dates: dict[str, dt.date] = {}
    current: dt.date | None = None
    for token in out.stdout.split("\0"):
        token = token.strip("\n")
        if not token:
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
            current = dt.date.fromisoformat(token)
        elif current:
            dates.setdefault(unicodedata.normalize("NFC", token), current)
    return dates


ARCHIVE = "Archive/"
# A commit by something other than synapsidian this recent, touching a file a run lists, most
# likely swept that run's change up (Obsidian Git commits everything on a timer).
SWEPT_WINDOW_S = 3 * 60 * 60
SWEPT_LOG = "swept-commits.jsonl"  # in the state dir: runs whose files another commit took


@dataclass(frozen=True, slots=True)
class CommitResult:
    sha: str | None
    archive_sources: list[str] = field(default_factory=list)  # old paths added for `Archive/...` moves
    swept: list[dict[str, str]] = field(default_factory=list)  # listed files someone else just committed


def commit(vault: Path, files: Sequence[str], message: str) -> CommitResult:
    """Commit exactly `files` (vault-relative), plus the old path of any note moved into Archive/.

    `git commit -- <paths>` commits only those paths even when something else is staged,
    so two runs that overlap in time can never sweep up each other's files.
    """
    listed = list(dict.fromkeys(files))
    sources = [src for f in listed if (src := _archive_source(vault, f)) and src not in listed]
    present = [f for f in [*listed, *sources] if (vault / f).exists() or _tracked(vault, f)]
    if not present:
        return CommitResult(None, sources)
    git(vault, "add", "--", *present)
    changed = set(git(vault, "diff", "--cached", "--name-only", "-z", "--", *present).stdout.split("\0")) - {""}
    swept = _swept(vault, [f for f in present if f not in changed])
    if not changed:
        return CommitResult(None, sources, swept)
    git(vault, "commit", "--quiet", "--no-verify", "-m", message, "--", *present)
    return CommitResult(git(vault, "rev-parse", "HEAD").stdout.strip(), sources, swept)


def _archive_source(vault: Path, rel: str) -> str | None:
    """`Archive/Inbox/x.md` → `Inbox/x.md` when that note was moved away (tracked, gone from disk)."""
    if not rel.startswith(ARCHIVE):
        return None
    source = rel.removeprefix(ARCHIVE)
    return source if not (vault / source).exists() and _tracked(vault, source) else None


def _swept(vault: Path, unchanged: Sequence[str]) -> list[dict[str, str]]:
    """Listed files with nothing to commit whose latest commit is a recent one not made by synapsidian."""
    swept = []
    now = time.time()
    for rel in unchanged:
        last = git(vault, "log", "-1", "--format=%h%x1f%ct%x1f%s", "--", rel, check=False).stdout.strip()
        if not last:
            continue
        sha, when, subject = last.split("\x1f", 2)
        if not subject.startswith("synapsidian(") and now - int(when) <= SWEPT_WINDOW_S:
            swept.append({"path": rel, "sha": sha, "message": subject})
    return swept


def _tracked(vault: Path, rel: str) -> bool:
    return git(vault, "ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0
