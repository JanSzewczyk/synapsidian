from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins" / "synapsidian"
WORK = ROOT / "plugins" / "synapsidian-work"
PROJECTS = ROOT / "plugins" / "synapsidian-projects"
SCRIPT_DIRS = (CORE / "scripts", WORK / "scripts")
FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture(autouse=True)
def _no_real_transcripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`sessions` scans Claude Code transcripts; never let a test read the developer's real ones."""
    monkeypatch.setenv("SYNAPSIDIAN_PROJECTS_DIR", str(tmp_path / "projects"))


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """An empty git-backed vault."""
    root = tmp_path / "Synapsidian"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    return root


def install_work_extension(root: Path) -> Path:
    """Put synapsidian-work's extension in the vault as `synapsidian setup extension` would, without the commit."""
    shutil.copytree(WORK / "extension", root / ".synapsidian" / "extensions" / "synapsidian-work")
    return root


def install_projects_extension(root: Path) -> Path:
    """Put synapsidian-projects' extension in the vault as `synapsidian setup extension` would, without the commit."""
    shutil.copytree(PROJECTS / "extension", root / ".synapsidian" / "extensions" / "synapsidian-projects")
    return root


@pytest.fixture
def work_vault(vault: Path) -> Path:
    """An empty git-backed vault with the synapsidian-work extension installed."""
    return install_work_extension(vault)


@pytest.fixture
def projects_vault(vault: Path) -> Path:
    """An empty git-backed vault with the synapsidian-projects extension installed."""
    return install_projects_extension(vault)


@pytest.fixture
def fixture_vault(tmp_path: Path) -> Path:
    """A copy of the 30-note synthetic vault, with both add-ons' extensions installed: it holds
    work notes and project notes."""
    target = tmp_path / "Fixture"
    shutil.copytree(FIXTURE_VAULT, target)
    return install_projects_extension(install_work_extension(target))


@pytest.fixture
def run(tmp_path: Path):
    """Run a plugin script as the skills do, returning (exit code, parsed JSON or raw stdout)."""

    def _run(
        script: str, *args: str, vault: Path | None = None, stdin: str | None = None, env: dict[str, str] | None = None
    ) -> tuple[int, object]:
        full_env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_PLUGIN", "SYNAPSIDIAN_"))}
        full_env["SYNAPSIDIAN_DATA"] = str(tmp_path / "data")
        # Never fall back to the developer's real Claude Code settings (and real vault).
        full_env["SYNAPSIDIAN_SETTINGS_FILE"] = str(tmp_path / "no-settings.json")
        full_env["SYNAPSIDIAN_PROJECTS_DIR"] = str(tmp_path / "projects")
        if vault is not None:
            full_env["SYNAPSIDIAN_VAULT"] = str(vault)
        full_env.update(env or {})
        path = next(d / f"{script}.py" for d in SCRIPT_DIRS if (d / f"{script}.py").is_file())
        proc = subprocess.run(
            [sys.executable, str(path), *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=full_env,
            cwd=tmp_path,
        )
        out = proc.stdout.strip()
        try:
            return proc.returncode, json.loads(out) if out else None
        except json.JSONDecodeError:
            return proc.returncode, out

    return _run
